import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { isJobFinished, useIngestDocumentAsync, useIngestionJob } from './ingestion'
import { apiClient } from './client'
import type { IngestionJob } from './types'

// Ingestion is queued rather than awaited (POST /ingest/async): the
// response is a job id, and the outcome arrives on a later poll. These
// tests pin the two things that go wrong when a client gets that wrong —
// polling forever after the job has settled, and treating the 202 as if
// it were the result.

function wrapper(client = new QueryClient({ defaultOptions: { queries: { retry: false } } })) {
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
  return { client, Wrapper }
}

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
  embedding_backend: 'onnx',
  finished_at: '2026-08-17T12:02:00Z',
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('useIngestDocumentAsync', () => {
  it('queues the upload instead of waiting for it', async () => {
    const postForm = vi.spyOn(apiClient, 'postForm').mockResolvedValue(job())
    const { Wrapper } = wrapper()

    const { result } = renderHook(() => useIngestDocumentAsync(), { wrapper: Wrapper })
    result.current.mutate({ file: new File(['x'], 'access_policy.pdf'), submitter: 'Sam' })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    // The endpoint, not /ingest: the synchronous one holds the request
    // open past nginx's read ceiling for exactly the large scanned
    // documents this product exists to handle.
    expect(postForm).toHaveBeenCalledWith('/ingest/async', expect.any(FormData))
    const form = postForm.mock.calls[0][1]
    expect(form.get('submitter')).toBe('Sam')
    expect(result.current.data?.status).toBe('queued')
  })

  it('omits the submitter field entirely when none was given', async () => {
    const postForm = vi.spyOn(apiClient, 'postForm').mockResolvedValue(job())
    const { Wrapper } = wrapper()

    const { result } = renderHook(() => useIngestDocumentAsync(), { wrapper: Wrapper })
    result.current.mutate({ file: new File(['x'], 'access_policy.pdf') })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(postForm.mock.calls[0][1].has('submitter')).toBe(false)
  })

  it('refreshes the job list on the 202, but not the document list', async () => {
    // A 202 means the work was accepted, not done. Refreshing the
    // documents here would show the reviewer a list that does not
    // contain the file they just uploaded, which reads as the upload
    // having failed. The job list is the opposite case: an accepted
    // upload missing from "Recent uploads" looks like one that was
    // never accepted at all.
    vi.spyOn(apiClient, 'postForm').mockResolvedValue(job())
    const { client, Wrapper } = wrapper()
    const invalidate = vi.spyOn(client, 'invalidateQueries')

    const { result } = renderHook(() => useIngestDocumentAsync(), { wrapper: Wrapper })
    result.current.mutate({ file: new File(['x'], 'access_policy.pdf') })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['ingestion-jobs', 'list'] })
    expect(invalidate).not.toHaveBeenCalledWith({ queryKey: ['documents', 'list'] })
    expect(invalidate).not.toHaveBeenCalledWith({ queryKey: ['evidence'] })
  })
})

describe('useIngestionJob', () => {
  it('polls a running job until it reaches an outcome', async () => {
    const get = vi
      .spyOn(apiClient, 'get')
      .mockResolvedValueOnce(job({ status: 'running' }))
      .mockResolvedValue(succeeded)
    const { Wrapper } = wrapper()

    const { result } = renderHook(() => useIngestionJob('job-1'), { wrapper: Wrapper })

    await waitFor(() => expect(result.current.data?.status).toBe('running'))
    expect(get).toHaveBeenCalledWith('/ingest/jobs/job-1')
    // Real timers: the poll interval is 2s, and faking it here would
    // test the mock rather than the interval the reviewer waits through.
    await waitFor(() => expect(result.current.data?.status).toBe('succeeded'), { timeout: 5000 })
  })

  it('stops polling once the job has settled', async () => {
    // A settled job is terminal in the data model, so further requests
    // could only ever return the same row — and this page is left open.
    const get = vi.spyOn(apiClient, 'get').mockResolvedValue(succeeded)
    const { Wrapper } = wrapper()

    const { result } = renderHook(() => useIngestionJob('job-1'), { wrapper: Wrapper })
    await waitFor(() => expect(result.current.data?.status).toBe('succeeded'))

    const callsAtCompletion = get.mock.calls.length
    await new Promise((resolve) => setTimeout(resolve, 2500))
    expect(get).toHaveBeenCalledTimes(callsAtCompletion)
  })

  it('makes the document linkable as soon as the job succeeds', async () => {
    // The synchronous hook could invalidate in onSuccess because its
    // response WAS the outcome. Here it has to happen on the poll that
    // observes "succeeded", or the reviewer uploads a document, switches
    // to the Evidence tab, and cannot find it.
    vi.spyOn(apiClient, 'get').mockResolvedValue(succeeded)
    const { client, Wrapper } = wrapper()
    const invalidate = vi.spyOn(client, 'invalidateQueries')

    const { result } = renderHook(() => useIngestionJob('job-1'), { wrapper: Wrapper })
    await waitFor(() => expect(result.current.data?.status).toBe('succeeded'))

    await waitFor(() =>
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ['documents', 'list'] }),
    )
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['evidence'] })
  })

  it('does not refresh anything for a job that failed', async () => {
    vi.spyOn(apiClient, 'get').mockResolvedValue(
      job({ status: 'failed', failure_category: 'unsupported_document' }),
    )
    const { client, Wrapper } = wrapper()
    const invalidate = vi.spyOn(client, 'invalidateQueries')

    const { result } = renderHook(() => useIngestionJob('job-1'), { wrapper: Wrapper })
    await waitFor(() => expect(result.current.data?.status).toBe('failed'))

    expect(invalidate).not.toHaveBeenCalled()
  })

  it('makes no request until there is a job to poll', async () => {
    const get = vi.spyOn(apiClient, 'get').mockResolvedValue(succeeded)
    const { Wrapper } = wrapper()

    renderHook(() => useIngestionJob(undefined), { wrapper: Wrapper })

    expect(get).not.toHaveBeenCalled()
  })
})

describe('isJobFinished', () => {
  it('treats only succeeded and failed as settled', () => {
    expect(isJobFinished(job({ status: 'queued' }))).toBe(false)
    expect(isJobFinished(job({ status: 'running' }))).toBe(false)
    expect(isJobFinished(job({ status: 'succeeded' }))).toBe(true)
    expect(isJobFinished(job({ status: 'failed' }))).toBe(true)
    // An unloaded job is not finished — mistaking undefined for settled
    // would stop the first poll before it ever happened.
    expect(isJobFinished(undefined)).toBe(false)
  })
})
