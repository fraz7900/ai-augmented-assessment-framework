import { AlertTriangle, FileText } from 'lucide-react'
import type { DocumentSummary } from '../api/types'

interface Props {
  documents: DocumentSummary[] | undefined
  isLoading: boolean
  value: string
  onChange: (documentId: string) => void
}

/**
 * Choose an ingested document by name instead of by UUID.
 *
 * This replaces a bare text input whose placeholder was literally "from
 * Upload" — the reviewer had to upload a file, copy a 36-character UUID
 * off the confirmation panel, navigate to a different screen, and paste
 * it in. Nothing validated the paste, so a truncated or stale id failed
 * at submit with a server error rather than being unselectable in the
 * first place.
 *
 * Three states worth distinguishing, because "nothing to show" and
 * "not loaded yet" mean different things to someone waiting:
 *
 * - loading: say so, rather than rendering an empty chooser that looks
 *   like "you have no documents".
 * - loaded but empty: say what to do about it. An empty dropdown with no
 *   explanation is the single most common dead end in an app like this.
 * - loaded with documents: a real list, newest first, showing filename
 *   and upload date, with superseded documents flagged (ADR-0050) so a
 *   reviewer does not cite a policy that has since been replaced.
 */
export default function DocumentPicker({ documents, isLoading, value, onChange }: Props) {
  if (isLoading) {
    return (
      <select disabled className="mt-1 w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-500">
        <option>Loading documents…</option>
      </select>
    )
  }

  if (!documents || documents.length === 0) {
    return (
      <div className="mt-1 flex items-start gap-2 rounded-md border border-dashed border-slate-300 bg-slate-50 px-3 py-2 text-sm text-slate-600">
        <FileText className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" aria-hidden="true" />
        <span>
          No documents ingested yet — upload one on the <strong>Upload</strong> tab first, then it
          will appear here.
        </span>
      </div>
    )
  }

  const selected = documents.find((d) => d.id === value)

  return (
    <div className="mt-1">
      <select
        id="document-id"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm"
      >
        <option value="">Select a document…</option>
        {documents.map((doc) => (
          <option key={doc.id} value={doc.id}>
            {doc.filename}
            {doc.is_superseded ? ' (superseded)' : ''} — {new Date(doc.uploaded_at).toLocaleDateString()}
          </option>
        ))}
      </select>

      {selected?.is_superseded && (
        <p className="mt-1 flex items-start gap-1.5 text-xs text-amber-700">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          <span>
            A newer document has replaced this one. Linking it is allowed — sometimes the older
            version is the one under review — but check that is what you intend.
          </span>
        </p>
      )}

      {/*
        The id stays visible after selection. It is what the API records,
        what appears in exports, and what someone will quote in a bug
        report, so hiding it entirely would trade one usability problem
        for another.
      */}
      {selected && (
        <p className="mt-1 font-mono text-[11px] text-slate-400">{selected.id}</p>
      )}
    </div>
  )
}
