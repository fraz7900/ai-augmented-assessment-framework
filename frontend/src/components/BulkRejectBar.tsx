import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import type { BulkReviewResult } from '../api/types'

// Bulk reject over a selection (ADR-0067). Reject only, and the asymmetry
// is the point: accepting an AI proposal creates a compliance claim that
// is scored, sealed and exported, so AGENTS.md rule 2 requires a human on
// each one. Rejecting withholds a claim and leaves the practice visible
// as a gap in the dashboard, where the next reviewer meets it again.
//
// Two things this control must keep true:
//
// 1. It acts on rows the person selected from what they were shown. It
//    has no "select everything above a confidence" affordance, because
//    that is the number deciding rather than the reviewer — the shape
//    ADR-0065 refused, and the reason the API takes ids rather than a
//    predicate.
// 2. It confirms before acting. A review decision is one-shot:
//    review_evidence refuses any link that is not pending, so a
//    rejection cannot be undone on that row.

export default function BulkRejectBar({
  selectedCount,
  isSubmitting,
  result,
  error,
  onReject,
  onClear,
}: {
  selectedCount: number
  isSubmitting: boolean
  result: BulkReviewResult | undefined
  error: Error | null
  onReject: (note: string | undefined) => void
  onClear: () => void
}) {
  const [isConfirming, setIsConfirming] = useState(false)
  const [note, setNote] = useState('')

  if (selectedCount === 0) {
    // Nothing selected: report the last outcome if there was one, then
    // get out of the way.
    if (result == null) return null
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-3 text-sm text-slate-700">
        Rejected {result.rejected_count} link(s).
        {result.skipped.length > 0 && (
          <span className="text-amber-700">
            {' '}
            {result.skipped.length} were already reviewed and were left as they were.
          </span>
        )}
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-slate-300 bg-slate-50 p-3">
      {!isConfirming ? (
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-sm font-medium text-slate-800">
            {selectedCount} link(s) selected
          </span>
          <button
            type="button"
            onClick={() => setIsConfirming(true)}
            className="rounded-md bg-red-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-600"
          >
            Reject selected
          </button>
          <button
            type="button"
            onClick={onClear}
            className="text-sm font-medium text-slate-600 underline underline-offset-2 hover:text-slate-800"
          >
            Clear selection
          </button>
          {/*
            There is no "Accept selected" here and there is no endpoint
            behind one. See the note at the top of this file.
          */}
        </div>
      ) : (
        <div className="space-y-2">
          <p className="text-sm font-medium text-slate-900">
            Reject {selectedCount} link(s)? This cannot be undone.
          </p>
          <p className="text-xs text-slate-600">
            Each practice goes back to being an unmet gap and stays in the dashboard's gap list. The
            documents stay attached, so evidence can be linked again by hand if this was wrong.
          </p>
          <div>
            <label className="block text-xs font-medium text-slate-700" htmlFor="bulk-reject-note">
              Note (optional, recorded on every link)
            </label>
            <input
              id="bulk-reject-note"
              type="text"
              value={note}
              onChange={(event) => setNote(event.target.value)}
              className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1 text-sm"
              placeholder="e.g. Retrieved text does not address this practice"
            />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              disabled={isSubmitting}
              onClick={() => {
                onReject(note.trim() || undefined)
                setIsConfirming(false)
                setNote('')
              }}
              className="inline-flex items-center gap-2 rounded-md bg-red-700 px-3 py-1.5 text-sm font-medium text-white enabled:hover:bg-red-600 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
              {isSubmitting ? 'Rejecting…' : `Yes, reject ${selectedCount}`}
            </button>
            <button
              type="button"
              onClick={() => setIsConfirming(false)}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-white"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
      {error && <p className="mt-2 text-sm text-red-700">{error.message}</p>}
    </div>
  )
}
