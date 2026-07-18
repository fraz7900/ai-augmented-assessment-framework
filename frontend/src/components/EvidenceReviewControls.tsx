import { useState } from 'react'
import type { EvidenceReviewStatus } from '../api/types'

// FR-13a / NFR-4: a human accept/edit/reject gate is a hard requirement,
// and re-reviewing an already-reviewed link must be prevented. This
// component is the enforcement point: once `reviewStatus` is no longer
// "pending", no review action is offered at all — not just disabled, but
// structurally absent, so there is nothing a reviewer could click to
// re-review a decision that already counts toward a score.
export default function EvidenceReviewControls({
  reviewStatus,
  onAccept,
  onReject,
  onEdit,
  isSubmitting = false,
}: {
  reviewStatus: EvidenceReviewStatus
  onAccept: () => void
  onReject: () => void
  onEdit: (correctedPracticeReference: string) => void
  isSubmitting?: boolean
}) {
  const [editing, setEditing] = useState(false)
  const [correctedReference, setCorrectedReference] = useState('')

  if (reviewStatus !== 'pending') {
    return <span className="text-xs text-slate-400">No action needed — already reviewed.</span>
  }

  if (editing) {
    return (
      <div className="flex items-center gap-2">
        <input
          type="text"
          value={correctedReference}
          onChange={(event) => setCorrectedReference(event.target.value)}
          placeholder="Corrected practice reference"
          aria-label="Corrected practice reference"
          className="rounded-md border border-slate-300 px-2 py-1 text-xs"
        />
        <button
          type="button"
          disabled={!correctedReference.trim() || isSubmitting}
          onClick={() => onEdit(correctedReference.trim())}
          className="rounded-md bg-blue-600 px-2 py-1 text-xs font-medium text-white disabled:opacity-50"
        >
          Save correction
        </button>
        <button
          type="button"
          onClick={() => setEditing(false)}
          className="text-xs text-slate-500 hover:underline"
        >
          Cancel
        </button>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        onClick={onAccept}
        disabled={isSubmitting}
        className="rounded-md bg-emerald-600 px-2 py-1 text-xs font-medium text-white disabled:opacity-50"
      >
        Accept
      </button>
      <button
        type="button"
        onClick={() => setEditing(true)}
        disabled={isSubmitting}
        className="rounded-md bg-blue-100 px-2 py-1 text-xs font-medium text-blue-800 disabled:opacity-50"
      >
        Edit
      </button>
      <button
        type="button"
        onClick={onReject}
        disabled={isSubmitting}
        className="rounded-md bg-red-100 px-2 py-1 text-xs font-medium text-red-800 disabled:opacity-50"
      >
        Reject
      </button>
    </div>
  )
}
