import { AlertTriangle, CheckCircle2, Loader2 } from 'lucide-react'
import type { FinalizationReadiness } from '../api/types'

interface Props {
  readiness: FinalizationReadiness | undefined
  isLoading: boolean
  /** Hidden once finalized — the checklist is about getting there. */
  isFinalized: boolean
}

/**
 * What stands between this assessment and finalization (ADR-0058).
 *
 * Rendered from the backend's machine-readable blocker categories, not
 * from parsed error text, and shown BEFORE the reviewer presses
 * Finalize rather than as a 409 afterwards.
 *
 * Deliberately silent about gaps. A finalized assessment that reports
 * an organization as non-compliant is a complete, legitimate result —
 * listing "you still have gaps" here would imply the platform wants
 * them hidden, which is the opposite of its purpose. What appears here
 * is unfinished *review work* only.
 */
export default function FinalizationChecklist({ readiness, isLoading, isFinalized }: Props) {
  if (isFinalized) return null

  if (isLoading) {
    return (
      <p className="mt-3 flex items-center gap-2 text-sm text-slate-500">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
        Checking finalization readiness…
      </p>
    )
  }

  if (!readiness) return null

  if (readiness.is_ready) {
    return (
      <p className="mt-3 flex items-start gap-2 rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">
        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
        <span>
          Ready to finalize — no unreviewed proposals, open evidence requests, or unsupported
          findings. Recorded gaps do not block finalization.
        </span>
      </p>
    )
  }

  return (
    <div
      className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900"
      data-testid="finalization-blockers"
    >
      <p className="flex items-center gap-2 font-medium">
        <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />
        {readiness.blockers.length} item(s) to resolve before finalizing
      </p>
      <ul className="mt-2 space-y-2">
        {readiness.blockers.map((blocker) => (
          <li key={blocker.category} className="flex gap-2">
            <span aria-hidden="true" className="text-amber-400">
              —
            </span>
            <span>
              {blocker.summary}
              {blocker.affected_ids.length > 0 && (
                <span className="mt-0.5 block font-mono text-[11px] text-amber-700">
                  {blocker.affected_ids.slice(0, 8).join(', ')}
                  {/*
                    count is the true total; affected_ids is capped by the
                    service. Saying "and N more" from the difference keeps
                    the two honest rather than implying the list is
                    complete.
                  */}
                  {blocker.count > Math.min(blocker.affected_ids.length, 8) &&
                    ` … and ${blocker.count - Math.min(blocker.affected_ids.length, 8)} more`}
                </span>
              )}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
