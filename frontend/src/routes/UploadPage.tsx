import { useState } from 'react'
import { AlertCircle, CheckCircle2, FileUp, Loader2, Upload } from 'lucide-react'
import { useIngestDocument } from '../api/ingestion'
import UploadProgress from '../components/UploadProgress'
import type { ParseStatus } from '../api/types'

// Sam (contributor persona): upload a document, nothing further — low
// friction is the point (services/document_parsers.py accepts PDF/DOCX/
// TXT/Markdown/XLSX/CSV specifically so Sam never needs to learn a
// structured format). Priya uses the same page, then copies the
// returned document_id into an assessment's Evidence tab.

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

const toneClasses: Record<'ok' | 'warn' | 'error', string> = {
  ok: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  warn: 'border-amber-200 bg-amber-50 text-amber-800',
  error: 'border-red-200 bg-red-50 text-red-800',
}

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null)
  const [submitter, setSubmitter] = useState('')
  const ingest = useIngestDocument()

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    if (!file) return
    ingest.mutate({ file, submitter: submitter || undefined })
  }

  return (
    <div className="max-w-xl">
      <h1 className="text-xl font-semibold text-slate-900">Upload evidence document</h1>
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
          <button
            type="submit"
            disabled={!file || ingest.isPending}
            className="inline-flex items-center gap-2 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white enabled:hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {ingest.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            ) : (
              <Upload className="h-4 w-4" aria-hidden="true" />
            )}
            {ingest.isPending ? 'Uploading…' : 'Upload document'}
          </button>
          {/*
            A disabled button with no explanation reads as broken. This
            says WHY it is disabled, which is the difference between "the
            app is stuck" and "I haven't chosen a file yet".
          */}
          {!file && !ingest.isPending && (
            <span className="text-sm text-slate-500">Choose a file to enable upload</span>
          )}
        </div>
      </form>

      <UploadProgress active={ingest.isPending} />

      {ingest.isError && (
        <div className="mt-4 flex items-start gap-2 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>{ingest.error.message}</span>
        </div>
      )}

      {ingest.isSuccess && (
        <div className="mt-4 space-y-2">
          <div className={`flex items-start gap-2 rounded-md border p-3 text-sm ${toneClasses[parseStatusMessages[ingest.data.parse_status].tone]}`}>
            {parseStatusMessages[ingest.data.parse_status].tone === 'ok' ? (
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            ) : (
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            )}
            <span>{parseStatusMessages[ingest.data.parse_status].message}</span>
          </div>
          {(ingest.data.parse_warnings?.length ?? 0) > 0 && (
            <ul className="list-inside list-disc text-sm text-amber-800">
              {ingest.data.parse_warnings!.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          )}
          <div className="rounded-md border border-slate-200 bg-white p-3 text-sm">
            <p className="text-slate-800">
              <span className="font-medium">{ingest.data.filename}</span> ·{' '}
              {ingest.data.chunk_count} passage(s) · embedded via {ingest.data.embedding_backend}
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
              {ingest.data.document_id}
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
