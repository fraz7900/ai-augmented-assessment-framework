import { useState } from 'react'
import { AlertCircle, CheckCircle2, Clock, FileUp, Loader2, Upload } from 'lucide-react'
import { useIngestDocumentAsync, useIngestionJob, useIngestionJobs } from '../api/ingestion'
import { useOrganizationScope } from '../lib/organizationContext'
import UploadProgress, { type UploadPhase } from '../components/UploadProgress'
import type { IngestionJob, IngestionJobFailure, ParseStatus } from '../api/types'

// Sam (contributor persona): upload a document, nothing further — low
// friction is the point (services/document_parsers.py accepts PDF/DOCX/
// TXT/Markdown/XLSX/CSV specifically so Sam never needs to learn a
// structured format). Priya uses the same page, then copies the
// returned document_id into an assessment's Evidence tab.
//
// The upload is queued rather than awaited: POST /ingest/async returns a
// job immediately and this page polls it. The synchronous endpoint held
// the request open for the whole parse/chunk/embed pass, which a large
// or scanned document pushes past nginx's 300s read ceiling — surfacing
// as a gateway error for an ingestion that was actually still running,
// and prompting exactly the re-upload that creates duplicates.

const parseStatusMessages: Record<ParseStatus, { tone: 'ok' | 'warn' | 'error'; message: string }> = {
  success: { tone: 'ok', message: 'Parsed successfully.' },
  // ADR-0055. Deliberately 'warn', not 'ok': the upload succeeded, but
  // OCR output is approximate, and the person uploading is the last one
  // in a position to notice that a page came back wrong. Telling them
  // here is cheaper than a reviewer discovering it inside a citation.
  success_ocr: {
    tone: 'warn',
    message:
      'Parsed successfully, but this document had no text layer — the text was recovered by ' +
      'local OCR and is approximate. Check any passage against the source page before relying ' +
      'on it as evidence.',
  },
  // A document that is part text layer, part scan. 'warn' for the same
  // reason as success_ocr, but the message has to say *some* rather than
  // all: most of this document is exact, and telling the uploader
  // otherwise would send them re-checking pages that never needed it.
  // The per-page detail is in the parse warnings shown alongside this.
  success_partial_ocr: {
    tone: 'warn',
    message:
      'Parsed successfully, but some pages of this document had no text layer and were read ' +
      'by local OCR. Text from those pages is approximate — check the listed pages against ' +
      'the source before relying on them as evidence.',
  },
  unsupported_scanned: {
    tone: 'warn',
    message:
      'This looks like a scanned document, and OCR could not recover usable text from it ' +
      '(it may be too low-resolution, blank, or handwritten).',
  },
  encoding_failure: { tone: 'error', message: 'The file could not be decoded (unsupported encoding).' },
  empty: { tone: 'warn', message: 'No text content was found in this document.' },
  failed: { tone: 'error', message: 'The file could not be parsed.' },
}

// What the reviewer should DO about each failure. The server's
// failure_message says what went wrong and is shown alongside; these say
// whether re-uploading the same file could possibly help, which is the
// one thing the message cannot tell them.
const failureGuidance: Record<IngestionJobFailure, string> = {
  unsupported_document:
    'Uploading the same file again will produce the same result. Try a version with a real text layer, or a clearer scan.',
  unknown_superseded_document:
    'The document this one was meant to supersede does not exist. Check the document ID and upload again.',
  too_large: 'The file is over the 25 MB limit. Split it, or upload the relevant section on its own.',
  // The one failure that is nobody's fault and is worth retrying
  // verbatim: the process stopped mid-ingest, so this job can never
  // finish, but the document itself was never the problem.
  interrupted:
    'The server restarted while this document was being processed, so the work stopped partway. Nothing was stored — upload it again.',
  internal_error:
    'This is a fault in the platform, not in the document. The details are in the server log; upload again once it has been looked at.',
}

const toneClasses: Record<'ok' | 'warn' | 'error', string> = {
  ok: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  warn: 'border-amber-200 bg-amber-50 text-amber-800',
  error: 'border-red-200 bg-red-50 text-red-800',
}

const statusLabels: Record<IngestionJob['status'], { label: string; className: string }> = {
  queued: { label: 'Queued', className: 'bg-slate-100 text-slate-700' },
  running: { label: 'Processing', className: 'bg-sky-100 text-sky-800' },
  succeeded: { label: 'Done', className: 'bg-emerald-100 text-emerald-800' },
  failed: { label: 'Failed', className: 'bg-red-100 text-red-800' },
}

function formatTime(iso: string): string {
  const parsed = new Date(iso)
  return Number.isNaN(parsed.getTime()) ? '' : parsed.toLocaleTimeString()
}

export default function UploadPage() {
  const { organizationId, organization } = useOrganizationScope()
  const [file, setFile] = useState<File | null>(null)
  const [submitter, setSubmitter] = useState('')
  const [jobId, setJobId] = useState<string | null>(null)
  const ingest = useIngestDocumentAsync()
  const polled = useIngestionJob(jobId ?? undefined)
  const recent = useIngestionJobs(organizationId)

  // The 202 response is itself a job row, so it fills the gap between
  // "queued" and the first poll coming back — without it the panel
  // would blink out of existence for one interval right after upload.
  const job: IngestionJob | undefined = polled.data ?? ingest.data

  const phase: UploadPhase | null = ingest.isPending
    ? 'uploading'
    : job?.status === 'queued' || job?.status === 'running'
      ? job.status
      : null

  const busy = phase !== null

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    if (!file || busy) return
    ingest.mutate(
      { file, submitter: submitter || undefined, organizationId },
      { onSuccess: (created) => setJobId(created.id) },
    )
  }

  const parse = job?.parse_status ? parseStatusMessages[job.parse_status] : null

  return (
    <div className="max-w-xl">
      <h1 className="text-xl font-semibold text-slate-900">Upload evidence document</h1>
      {/* Whose evidence this becomes, said before the file is chosen
          rather than after it is ingested (ADR-0063): a document filed
          under the wrong client cannot be moved to the right one. */}
      <p className="text-sm text-slate-500">
        Uploading to <span className="font-medium text-slate-700">{organization?.name ?? '…'}</span>
      </p>
      <p className="mt-1 text-sm text-slate-600">
        PDF, DOCX, TXT, Markdown, XLSX, or CSV. After ingestion, copy the document ID below into
        an assessment&apos;s Evidence tab to link it to a practice.
      </p>

      <form onSubmit={handleSubmit} className="mt-4 space-y-4">
        <div>
          <label className="block text-sm font-medium text-slate-700" htmlFor="file">
            File
          </label>
          <input
            id="file"
            type="file"
            accept=".pdf,.docx,.txt,.md,.xlsx,.csv"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            className="mt-1 block w-full cursor-pointer rounded-md border border-slate-300 p-2 text-sm text-slate-700 file:mr-3 file:rounded-md file:border-0 file:bg-slate-100 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-slate-900 hover:file:bg-slate-200"
          />
          {/*
            Confirm the chosen file and its size. The size matters here
            specifically: uploads are capped at 25MB, and a reviewer who
            picks a 60MB scan should learn that before waiting for a
            rejection.
          */}
          {file && (
            <p className="mt-1.5 flex items-center gap-1.5 text-sm text-slate-600">
              <FileUp className="h-4 w-4 shrink-0 text-slate-400" aria-hidden="true" />
              <span className="font-medium text-slate-800">{file.name}</span>
              <span className="text-slate-500">({(file.size / 1024 / 1024).toFixed(1)} MB)</span>
              {file.size > 25 * 1024 * 1024 && (
                <span className="font-medium text-red-700">— over the 25 MB limit</span>
              )}
            </p>
          )}
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700" htmlFor="submitter">
            Submitter (optional)
          </label>
          <input
            id="submitter"
            type="text"
            value={submitter}
            onChange={(event) => setSubmitter(event.target.value)}
            className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm"
            placeholder="e.g. Sam Rivera"
          />
        </div>
        <div className="flex items-center gap-3">
          {/*
            Disabled for the whole job, not just the POST. The upload
            call now returns in a second or so while the actual work runs
            for minutes; re-enabling at that point would invite the
            double-upload this page has already been bitten by once.
          */}
          <button
            type="submit"
            disabled={!file || busy}
            className="inline-flex items-center gap-2 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white enabled:hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            ) : (
              <Upload className="h-4 w-4" aria-hidden="true" />
            )}
            {busy ? 'Uploading…' : 'Upload document'}
          </button>
          {/*
            A disabled button with no explanation reads as broken. This
            says WHY it is disabled, which is the difference between "the
            app is stuck" and "I haven't chosen a file yet".
          */}
          {!file && !busy && (
            <span className="text-sm text-slate-500">Choose a file to enable upload</span>
          )}
        </div>
      </form>

      <UploadProgress phase={phase} />

      {ingest.isError && (
        <div className="mt-4 flex items-start gap-2 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>{ingest.error.message}</span>
        </div>
      )}

      {/*
        A job that failed is not an error in the HTTP sense — the upload
        was accepted and the server answered every poll correctly. It
        still has to read as a failure to the person who uploaded it,
        which is the whole reason the job row survives failure rather
        than being discarded.
      */}
      {job?.status === 'failed' && (
        <div className="mt-4 space-y-2">
          <div className={`flex items-start gap-2 rounded-md border p-3 text-sm ${toneClasses.error}`}>
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <span>
              <span className="font-medium">{job.filename}</span> could not be ingested.{' '}
              {job.failure_message}{' '}
              {job.failure_category && failureGuidance[job.failure_category]}
            </span>
          </div>
          {(job.parse_warnings?.length ?? 0) > 0 && (
            <ul className="list-inside list-disc text-sm text-amber-800">
              {job.parse_warnings!.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {job?.status === 'succeeded' && (
        <div className="mt-4 space-y-2">
          {parse && (
            <div className={`flex items-start gap-2 rounded-md border p-3 text-sm ${toneClasses[parse.tone]}`}>
              {parse.tone === 'ok' ? (
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
              ) : (
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
              )}
              <span>{parse.message}</span>
            </div>
          )}
          {(job.parse_warnings?.length ?? 0) > 0 && (
            <ul className="list-inside list-disc text-sm text-amber-800">
              {job.parse_warnings!.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          )}
          <div className="rounded-md border border-slate-200 bg-white p-3 text-sm">
            <p className="text-slate-800">
              <span className="font-medium">{job.filename}</span> · {job.chunk_count} passage(s) ·
              embedded via {job.embedding_backend}
            </p>
            {/*
              The id is kept, but demoted. It used to be the headline
              here because linking evidence required copying it into
              another screen by hand; the Evidence tab now offers a
              chooser, so this is reference information rather than a
              step the reviewer has to act on.
            */}
            <p className="mt-1 text-xs text-slate-500">
              Ready to link — open an assessment&apos;s <strong>Evidence</strong> tab and pick it
              from the document list.
            </p>
            <p className="mt-1 select-all font-mono text-[11px] text-slate-400">
              {job.document_id}
            </p>
          </div>
        </div>
      )}

      {/*
        Recent uploads. This is what makes leaving the page safe: the
        outcome no longer arrives in the upload's own response, so
        without a list, a reviewer who navigated away mid-ingest has no
        way to find out whether their document landed — and "is it in
        the document list?" cannot tell a still-running ingestion apart
        from a failed one.
      */}
      {(recent.data?.length ?? 0) > 0 && (
        <section className="mt-8">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-900">
            <Clock className="h-4 w-4 text-slate-400" aria-hidden="true" />
            Recent uploads
          </h2>
          <ul className="mt-2 divide-y divide-slate-100 rounded-md border border-slate-200 bg-white">
            {recent.data!.map((entry) => (
              <li key={entry.id} className="flex items-baseline gap-2 px-3 py-2 text-sm">
                <span
                  className={`shrink-0 rounded px-1.5 py-0.5 text-xs font-medium ${statusLabels[entry.status].className}`}
                >
                  {statusLabels[entry.status].label}
                </span>
                <span className="truncate font-medium text-slate-800">{entry.filename}</span>
                <span className="ml-auto shrink-0 text-xs text-slate-500">
                  {entry.status === 'succeeded'
                    ? `${entry.chunk_count} passage(s)`
                    : formatTime(entry.created_at)}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
