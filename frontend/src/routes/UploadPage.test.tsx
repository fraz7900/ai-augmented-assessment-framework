import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import UploadPage from './UploadPage'
import { OrganizationProvider } from '../lib/organization'
import { ApiError, apiClient } from '../api/client'
import type { IngestionJob, Organization } from '../api/types'

// The upload no longer carries its own outcome: POST /ingest/async
// returns a job and this page polls it. That moves three things onto
// the page that used to be free — the outcome has to arrive on a poll,
// a failed job has to read as a failure even though every HTTP call
// succeeded, and the reviewer has to be stopped from uploading the same
// file twice while the first copy is still being processed.

function job(overrides: Partial<IngestionJob> = {}): IngestionJob {
  return {
    id: 'job-1',
    status: 'queued',
    filename: 'access_policy.pdf',
    submitter: null,
    supersedes_document_id: null,
    created_at: '2026-08-17T12:00:00Z',
    started_at: null,
    finished_at: null,
    document_id: null,
    chunk_count: null,
    parse_status: null,
    parser_version: null,
    embedding_backend: null,
    parse_warnings: [],
    failure_category: null,
    failure_message: null,
    ...overrides,
  }
}

const succeeded = job({
  status: 'succeeded',
  document_id: 'doc-9',
  chunk_count: 148,
  parse_status: 'success',
  parser_version: 'pypdf==6.16.0',
  embedding_backend: 'onnx',
  finished_at: '2026-08-17T12:02:00Z',
})

// The page is scoped to one organisation (ADR-0063), so it renders
// inside the provider the app shell supplies.
const ORGANIZATION: Organization = {
  id: 'org_default',
  name: 'Unassigned',
  created_at: '2026-08-19T12:00:00Z',
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>
      <OrganizationProvider>{children}</OrganizationProvider>
    </QueryClientProvider>
  )
  return render(<UploadPage />, { wrapper })
}

/** Route GETs by path: the page polls one job and lists recent ones. */
function stubGets(polled: IngestionJob, recent: IngestionJob[] = []) {
  return vi
    .spyOn(apiClient, 'get')
    .mockImplementation(async (path: string) => {
      if (path.startsWith('/organizations')) return [ORGANIZATION]
      return path.startsWith('/ingest/jobs?') ? recent : polled
    })
}

async function uploadAFile() {
  const user = userEvent.setup()
  await user.upload(
    screen.getByLabelText('File'),
    new File(['policy text'], 'access_policy.pdf', { type: 'application/pdf' }),
  )
  await user.click(screen.getByRole('button', { name: /upload document/i }))
  return user
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('UploadPage', () => {
  it('queues the document and reports the outcome the poll returns', async () => {
    const postForm = vi.spyOn(apiClient, 'postForm').mockResolvedValue(job())
    stubGets(succeeded)

    renderPage()
    await uploadAFile()

    expect(postForm).toHaveBeenCalledWith('/ingest/async', expect.any(FormData))
    await waitFor(() => expect(screen.getByText(/parsed successfully/i)).toBeInTheDocument())
    expect(screen.getByText(/148 passage\(s\)/)).toBeInTheDocument()
    // The id is demoted but still present — it is the reference a
    // reviewer falls back to when the Evidence tab chooser is ambiguous.
    expect(screen.getByText('doc-9')).toBeInTheDocument()
  })

  it('keeps Upload disabled while the queued work is still running', async () => {
    // The POST now returns in about a second while the work runs for
    // minutes. Re-enabling the button when the POST resolves would
    // invite the double-upload that once put three copies of one
    // document into the store.
    vi.spyOn(apiClient, 'postForm').mockResolvedValue(job())
    stubGets(job({ status: 'running', started_at: '2026-08-17T12:00:05Z' }))

    renderPage()
    await uploadAFile()

    await waitFor(() => expect(screen.getByText(/processing document/i)).toBeInTheDocument())
    expect(screen.getByRole('button', { name: /uploading/i })).toBeDisabled()
  })

  it('says a job is queued rather than calling it processing', async () => {
    // A queued job is waiting, not working. Reporting it as processing
    // would be a number this codebase cannot support — and "queued"
    // explains a wait that would otherwise look like a stall.
    vi.spyOn(apiClient, 'postForm').mockResolvedValue(job())
    stubGets(job({ status: 'queued' }))

    renderPage()
    await uploadAFile()

    await waitFor(() => expect(screen.getByText(/^Queued…/)).toBeInTheDocument())
    expect(screen.queryByText(/processing document/i)).not.toBeInTheDocument()
  })

  it('shows a failed job as a failure, with what to do about it', async () => {
    // Every HTTP call here succeeded — the job simply failed. Without
    // this branch the page would sit on "Processing" forever and the
    // reviewer would never learn the document was rejected.
    vi.spyOn(apiClient, 'postForm').mockResolvedValue(job())
    stubGets(
      job({
        status: 'failed',
        failure_category: 'unsupported_document',
        failure_message: 'The document could not be used (unsupported_scanned).',
        parse_warnings: ['OCR recovered no text from any of 12 pages.'],
      }),
    )

    renderPage()
    await uploadAFile()

    await waitFor(() => expect(screen.getByText(/could not be ingested/i)).toBeInTheDocument())
    expect(screen.getByText(/unsupported_scanned/)).toBeInTheDocument()
    // The guidance the server's message cannot give: whether retrying
    // the same file could possibly help.
    expect(screen.getByText(/will produce the same result/i)).toBeInTheDocument()
    expect(screen.getByText(/OCR recovered no text/i)).toBeInTheDocument()
  })

  it('tells an interrupted job apart from a rejected one', async () => {
    // The one failure worth retrying verbatim: the process stopped
    // mid-ingest, so the job can never finish, but nothing was wrong
    // with the document.
    vi.spyOn(apiClient, 'postForm').mockResolvedValue(job())
    stubGets(
      job({
        status: 'failed',
        failure_category: 'interrupted',
        failure_message: 'Interrupted by a restart.',
      }),
    )

    renderPage()
    await uploadAFile()

    await waitFor(() => expect(screen.getByText(/upload it again/i)).toBeInTheDocument())
  })

  it('surfaces the queue-full refusal instead of failing silently', async () => {
    vi.spyOn(apiClient, 'postForm').mockRejectedValue(
      new ApiError(
        '10 documents are already queued or in progress (limit 10). Wait for one to finish before uploading another.',
        429,
      ),
    )
    stubGets(succeeded)

    renderPage()
    await uploadAFile()

    await waitFor(() =>
      expect(screen.getByText(/already queued or in progress/i)).toBeInTheDocument(),
    )
    // Refused, so nothing is in flight — the reviewer must be able to
    // try again once the queue drains.
    expect(screen.getByRole('button', { name: /upload document/i })).toBeEnabled()
  })

  it('lists recent uploads so a reviewer who left the page can find the outcome', async () => {
    stubGets(
      succeeded,
      [
        succeeded,
        job({ id: 'job-2', filename: 'incident_plan.pdf', status: 'failed' }),
        job({ id: 'job-3', filename: 'backup_runbook.pdf', status: 'running' }),
      ],
    )

    renderPage()

    await waitFor(() => expect(screen.getByText('Recent uploads')).toBeInTheDocument())
    expect(screen.getByText('incident_plan.pdf')).toBeInTheDocument()
    expect(screen.getByText('backup_runbook.pdf')).toBeInTheDocument()
    // Status is stated per row: "is it in the document list?" cannot
    // tell a running ingestion apart from a failed one.
    expect(screen.getByText('Failed')).toBeInTheDocument()
    expect(screen.getByText('Processing')).toBeInTheDocument()
    expect(screen.getByText('Done')).toBeInTheDocument()
  })
})
