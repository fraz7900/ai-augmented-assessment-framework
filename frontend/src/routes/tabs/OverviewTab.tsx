import { useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import { useStatusHistory, useTransitionStatus } from '../../api/assessments'
import StatusBadge from '../../components/StatusBadge'
import type { AssessmentTabContext } from '../AssessmentDetailPage'
import type { AssessmentStatus } from '../../api/types'

// Diane (Internal Audit persona): needs the complete, immutable status
// history to confirm a finalized assessment cannot be silently altered
// (AssessmentFinalizedError in services/assessment_service.py).

const nextStatus: Partial<Record<AssessmentStatus, AssessmentStatus>> = {
  draft: 'in_review',
  in_review: 'finalized',
}

export default function OverviewTab() {
  const { assessmentId, assessment } = useOutletContext<AssessmentTabContext>()
  const { data: history, isLoading, isError, error } = useStatusHistory(assessmentId)
  const transition = useTransitionStatus(assessmentId)
  const [note, setNote] = useState('')

  const target = nextStatus[assessment.status]

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="font-semibold text-slate-900">Status</h2>
        <p className="mt-1 text-sm text-slate-600">
          Currently <StatusBadge status={assessment.status} />
        </p>

        {target ? (
          <div className="mt-3 flex flex-wrap items-end gap-3">
            <div>
              <label className="block text-sm font-medium text-slate-700" htmlFor="transition-note">
                Note (optional)
              </label>
              <input
                id="transition-note"
                type="text"
                value={note}
                onChange={(event) => setNote(event.target.value)}
                className="mt-1 rounded-md border border-slate-300 px-3 py-1.5 text-sm"
              />
            </div>
            <button
              type="button"
              onClick={() =>
                transition.mutate(
                  { status: target, note: note || undefined },
                  { onSuccess: () => setNote('') },
                )
              }
              disabled={transition.isPending}
              className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              {transition.isPending ? 'Updating…' : `Advance to ${target.replace('_', ' ')}`}
            </button>
          </div>
        ) : (
          <p className="mt-2 text-sm text-slate-500">
            Finalized — evidence and status are locked (audit-immutability guarantee).
          </p>
        )}
        {transition.isError && <p className="mt-2 text-sm text-red-700">{transition.error.message}</p>}
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="font-semibold text-slate-900">Status history</h2>
        {isLoading && <p className="mt-2 text-sm text-slate-500">Loading…</p>}
        {isError && <p className="mt-2 text-sm text-red-700">{error.message}</p>}
        {history && history.length > 0 && (
          <table className="mt-2 w-full text-left text-sm">
            <thead className="text-slate-500">
              <tr>
                <th className="py-1 font-medium">From</th>
                <th className="py-1 font-medium">To</th>
                <th className="py-1 font-medium">Note</th>
                <th className="py-1 font-medium">Changed at</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {history.map((change) => (
                <tr key={change.id}>
                  <td className="py-1 text-slate-600">{change.from_status ?? '—'}</td>
                  <td className="py-1 text-slate-900">{change.to_status}</td>
                  <td className="py-1 text-slate-600">{change.note ?? '—'}</td>
                  <td className="py-1 text-slate-500">
                    {change.changed_at ? new Date(change.changed_at).toLocaleString() : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
