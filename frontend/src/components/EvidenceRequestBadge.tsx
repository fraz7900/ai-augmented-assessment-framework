import { useState } from 'react'
import type { EvidenceRequest } from '../api/types'

// ADR-0043: one open evidence request shown against its gap, with an
// explicit "mark resolved" action -- never inferred from a new
// evidence link being added, since linking evidence doesn't guarantee
// it actually addresses what was requested.
export default function EvidenceRequestBadge({
  request,
  isDisabled = false,
  isSubmitting = false,
  onResolve,
}: {
  request: EvidenceRequest
  isDisabled?: boolean
  isSubmitting?: boolean
  onResolve: (resolvedBy: string) => void
}) {
  const [resolving, setResolving] = useState(false)
  const [resolvedBy, setResolvedBy] = useState('')

  return (
    <div className="mt-1 rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-xs text-amber-800">
      <span className="font-medium">Evidence requested</span> ({request.requested_by}):{' '}
      {request.note}
      {!isDisabled &&
        (resolving ? (
          <div className="mt-1 flex items-center gap-2">
            <input
              type="text"
              value={resolvedBy}
              onChange={(event) => setResolvedBy(event.target.value)}
              placeholder="Your name"
              aria-label="Resolved by"
              className="rounded-md border border-slate-300 px-2 py-0.5 text-xs"
            />
            <button
              type="button"
              disabled={!resolvedBy.trim() || isSubmitting}
              onClick={() => {
                onResolve(resolvedBy.trim())
                setResolving(false)
                setResolvedBy('')
              }}
              className="rounded-md bg-amber-600 px-2 py-0.5 text-xs font-medium text-white disabled:opacity-50"
            >
              {isSubmitting ? 'Saving…' : 'Confirm resolved'}
            </button>
            <button
              type="button"
              onClick={() => setResolving(false)}
              className="text-xs text-slate-500 hover:underline"
            >
              Cancel
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setResolving(true)}
            className="ml-2 font-medium text-amber-700 hover:underline"
          >
            Mark resolved
          </button>
        ))}
    </div>
  )
}
