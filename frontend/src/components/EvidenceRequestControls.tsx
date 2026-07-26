import { useState } from 'react'

// ADR-0043: a reviewer's explicit request that someone go find and
// upload more evidence for this practice -- a workflow action distinct
// from PracticeFindingControls' compliance judgment; both can coexist
// for the same gap. note/requestedBy are both required server-side
// (MissingEvidenceRequestNoteError), so this form can't submit without
// them -- structural enforcement, matching PracticeFindingControls'
// own convention.
export default function EvidenceRequestControls({
  isDisabled = false,
  isSubmitting = false,
  onSubmit,
}: {
  isDisabled?: boolean
  isSubmitting?: boolean
  onSubmit: (note: string, requestedBy: string) => void
}) {
  const [open, setOpen] = useState(false)
  const [note, setNote] = useState('')
  const [requestedBy, setRequestedBy] = useState('')

  if (isDisabled) return null

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="text-xs font-medium text-amber-700 hover:underline"
      >
        Request more evidence
      </button>
    )
  }

  return (
    <div className="mt-2 flex flex-col gap-2 rounded-md border border-amber-200 bg-amber-50 p-2">
      <textarea
        value={note}
        onChange={(event) => setNote(event.target.value)}
        placeholder="What specifically is needed? (required)"
        aria-label="Evidence request note"
        rows={2}
        className="rounded-md border border-slate-300 px-2 py-1 text-xs"
      />
      <input
        type="text"
        value={requestedBy}
        onChange={(event) => setRequestedBy(event.target.value)}
        placeholder="Your name"
        aria-label="Requested by"
        className="rounded-md border border-slate-300 px-2 py-1 text-xs"
      />
      <div className="flex items-center gap-2">
        <button
          type="button"
          disabled={!note.trim() || !requestedBy.trim() || isSubmitting}
          onClick={() => {
            onSubmit(note.trim(), requestedBy.trim())
            setOpen(false)
            setNote('')
          }}
          className="rounded-md bg-amber-600 px-2 py-1 text-xs font-medium text-white disabled:opacity-50"
        >
          {isSubmitting ? 'Sending…' : 'Send request'}
        </button>
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="text-xs text-slate-500 hover:underline"
        >
          Cancel
        </button>
      </div>
    </div>
  )
}
