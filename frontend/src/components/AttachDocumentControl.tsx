import { useState } from 'react'
import { Paperclip } from 'lucide-react'
import type { DocumentSummary } from '../api/types'

interface Props {
  /** Every document on the instance — what this control browses. */
  allDocuments: DocumentSummary[] | undefined
  /** Already attached to this assessment, so not offered again. */
  attachedIds: string[]
  isDisabled?: boolean
  isSubmitting?: boolean
  onAttach: (documentId: string) => void
}

/**
 * Bring a document into this assessment (ADR-0062).
 *
 * The evidence chooser lists only what is already attached, which is
 * the whole point — one organisation's policies must not appear while
 * assessing another's. This is the deliberate step across that line,
 * and it is separate from linking on purpose: attaching says the
 * document belongs to this assessment, linking says a specific passage
 * of it satisfies a specific practice. The mapping engine needs the
 * first before it can propose the second.
 */
export default function AttachDocumentControl({
  allDocuments,
  attachedIds,
  isDisabled = false,
  isSubmitting = false,
  onAttach,
}: Props) {
  const [open, setOpen] = useState(false)
  const [selected, setSelected] = useState('')

  if (isDisabled) return null

  const available = (allDocuments ?? []).filter((doc) => !attachedIds.includes(doc.id))

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-700 hover:underline"
      >
        <Paperclip className="h-3.5 w-3.5" aria-hidden="true" />
        Attach a document
      </button>
    )
  }

  return (
    <div className="mt-2 flex flex-wrap items-center gap-2 rounded-md border border-slate-200 bg-slate-50 p-2">
      {available.length === 0 ? (
        // Distinguishing "nothing ingested" from "everything already
        // attached" — the same distinction DocumentPicker draws, for the
        // same reason: an empty dropdown with no explanation reads as
        // broken.
        <p className="text-xs text-slate-600">
          {(allDocuments?.length ?? 0) === 0
            ? 'No documents have been ingested yet. Upload one first.'
            : 'Every ingested document is already attached to this assessment.'}
        </p>
      ) : (
        <>
          <select
            value={selected}
            onChange={(event) => setSelected(event.target.value)}
            aria-label="Document to attach"
            className="rounded-md border border-slate-300 px-2 py-1 text-xs"
          >
            <option value="">Choose a document…</option>
            {available.map((doc) => (
              <option key={doc.id} value={doc.id}>
                {doc.filename}
                {doc.is_superseded ? ' (superseded)' : ''}
              </option>
            ))}
          </select>
          <button
            type="button"
            disabled={!selected || isSubmitting}
            onClick={() => {
              onAttach(selected)
              setSelected('')
              setOpen(false)
            }}
            className="rounded-md bg-slate-900 px-2 py-1 text-xs font-medium text-white disabled:opacity-50"
          >
            {isSubmitting ? 'Attaching…' : 'Attach'}
          </button>
        </>
      )}
      <button
        type="button"
        onClick={() => setOpen(false)}
        className="text-xs text-slate-500 hover:underline"
      >
        Cancel
      </button>
    </div>
  )
}
