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
  onResolve: () => void
}) {
  // Resolution is attributed to the authenticated identity, so this no
  // longer asks who is doing it (ADR-0061). What remains is the
  // confirmation step itself, which ADR-0043 requires: resolving is
  // always explicit, never inferred from evidence appearing.
  const [resolving, setResolving] = useState(false)

  return (
    <div className="mt-1 rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-xs text-amber-800">
      <span className="font-medium">Evidence requested</span> ({request.requested_by}):{' '}
      {request.note}
      {!isDisabled &&
        (resolving ? (
          <div className="mt-1 flex items-center gap-2">
            <span>Mark this request resolved?</span>
            <button
              type="button"
              disabled={isSubmitting}
              onClick={() => {
                onResolve()
                setResolving(false)
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
