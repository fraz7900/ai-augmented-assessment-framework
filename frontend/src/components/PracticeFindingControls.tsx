import { useState } from 'react'
import type { PracticeFindingStatus } from '../api/types'

const OPTIONS: { value: PracticeFindingStatus; label: string }[] = [
  { value: 'satisfied', label: 'Satisfied' },
  { value: 'partially_satisfied', label: 'Partially satisfied' },
  { value: 'not_satisfied', label: 'Not satisfied' },
  { value: 'insufficient_evidence', label: 'Insufficient evidence' },
  { value: 'not_applicable', label: 'Not applicable' },
]

// ADR-0030: a rationale is required server-side for every finding — this
// form can't submit without one, so a reviewer never records a judgment
// with no stated reason (mirrors EvidenceReviewControls.tsx's "structural
// enforcement, not just a disabled button" convention).
export default function PracticeFindingControls({
  isDisabled = false,
  isSubmitting = false,
  onSubmit,
}: {
  isDisabled?: boolean
  isSubmitting?: boolean
  onSubmit: (status: PracticeFindingStatus, rationale: string) => void
}) {
  const [open, setOpen] = useState(false)
  const [status, setStatus] = useState<PracticeFindingStatus>('not_satisfied')
  const [rationale, setRationale] = useState('')

  if (isDisabled) return null

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="text-xs font-medium text-blue-700 hover:underline"
      >
        Record finding
      </button>
    )
  }

  return (
    <div className="mt-2 flex flex-col gap-2 rounded-md border border-slate-200 bg-slate-50 p-2">
      <select
        value={status}
        onChange={(event) => setStatus(event.target.value as PracticeFindingStatus)}
        aria-label="Finding status"
        className="rounded-md border border-slate-300 px-2 py-1 text-xs"
      >
        {OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <textarea
        value={rationale}
        onChange={(event) => setRationale(event.target.value)}
        placeholder="Rationale (required) — why does this finding apply?"
        aria-label="Finding rationale"
        rows={2}
        className="rounded-md border border-slate-300 px-2 py-1 text-xs"
      />
      <div className="flex items-center gap-2">
        <button
          type="button"
          disabled={!rationale.trim() || isSubmitting}
          onClick={() => {
            onSubmit(status, rationale.trim())
            setOpen(false)
            setRationale('')
          }}
          className="rounded-md bg-blue-600 px-2 py-1 text-xs font-medium text-white disabled:opacity-50"
        >
          {isSubmitting ? 'Saving…' : 'Save finding'}
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
