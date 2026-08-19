import { useState } from 'react'
import { useIdentity } from '../api/identity'

// ADR-0043: a reviewer's explicit request that someone go find and
// upload more evidence for this practice -- a workflow action distinct
// from PracticeFindingControls' compliance judgment; both can coexist
// for the same gap. The note is required server-side
// (MissingEvidenceRequestNoteError), so this form can't submit without
// it -- structural enforcement, matching PracticeFindingControls' own
// convention.
//
// It used to ask for the requester's name too. Since ADR-0061 the
// server attributes the request to the authenticated identity and
// ignores anything the client claims, so asking would invite someone to
// type a name that will not be used. The identity is shown instead:
// removing the field without saying what replaced it would leave a
// reviewer recording decisions under a name they cannot see.
export default function EvidenceRequestControls({
  isDisabled = false,
  isSubmitting = false,
  onSubmit,
}: {
  isDisabled?: boolean
  isSubmitting?: boolean
  onSubmit: (note: string) => void
}) {
  const [open, setOpen] = useState(false)
  const [note, setNote] = useState('')
  const { data: identity } = useIdentity()

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
      {identity && (
        <p className="text-xs text-amber-900">
          {identity.is_authenticated ? (
            <>
              Recorded as <span className="font-medium">{identity.actor}</span>
            </>
          ) : (
            // Worth saying rather than hiding: a deployment that is not
            // behind the authenticating proxy records every request
            // anonymously, and the person making it should know that
            // before they make it.
            <>This request will be recorded without an identity — you are not signed in.</>
          )}
        </p>
      )}
      <div className="flex items-center gap-2">
        <button
          type="button"
          disabled={!note.trim() || isSubmitting}
          onClick={() => {
            onSubmit(note.trim())
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
