import { useState } from 'react'
import { useIngestDocument } from '../api/ingestion'
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
            className="mt-1 block w-full text-sm text-slate-700"
          />
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
        <button
          type="submit"
          disabled={!file || ingest.isPending}
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {ingest.isPending ? 'Uploading…' : 'Upload'}
        </button>
      </form>

      {ingest.isError && (
        <div className="mt-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          {ingest.error.message}
        </div>
      )}

      {ingest.isSuccess && (
        <div className="mt-4 space-y-2">
          <div className={`rounded-md border p-3 text-sm ${toneClasses[parseStatusMessages[ingest.data.parse_status].tone]}`}>
            {parseStatusMessages[ingest.data.parse_status].message}
          </div>
          {(ingest.data.parse_warnings?.length ?? 0) > 0 && (
            <ul className="list-inside list-disc text-sm text-amber-800">
              {ingest.data.parse_warnings!.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          )}
          <div className="rounded-md border border-slate-200 bg-white p-3 text-sm">
            <p>
              <span className="font-medium">Document ID:</span>{' '}
              <span className="select-all font-mono text-xs">{ingest.data.document_id}</span>
            </p>
            <p className="text-slate-600">
              {ingest.data.filename} · {ingest.data.chunk_count} chunk(s) · embedded via{' '}
              {ingest.data.embedding_backend}
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
