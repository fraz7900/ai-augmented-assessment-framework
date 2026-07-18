import { useOutletContext } from 'react-router-dom'
import { reportUrl, useDashboard } from '../../api/assessments'
import ScoreHeadline from '../../components/ScoreHeadline'
import GapGroup from '../../components/GapGroup'
import ResolutionList from '../../components/ResolutionList'
import type { AssessmentTabContext } from '../AssessmentDetailPage'

// executive-reporting skill: lead with situation/complication/resolution,
// not a raw score table (Marcus/CISO persona, US-6.1) — this renders
// DashboardReport's three sections verbatim, in that order, with no
// client-side re-derivation of any number.
export default function DashboardTab() {
  const { assessmentId } = useOutletContext<AssessmentTabContext>()
  const { data: dashboard, isLoading, isError, error } = useDashboard(assessmentId)

  if (isLoading) return <p className="text-sm text-slate-500">Loading…</p>
  if (isError) return <p className="text-sm text-red-700">{error.message}</p>
  if (!dashboard) return null

  const { situation, overall, complication, resolution } = dashboard

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-semibold text-slate-900">Situation</h2>
        <div className="flex gap-2">
          <a
            href={reportUrl(assessmentId, 'pdf')}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Download PDF
          </a>
          <a
            href={reportUrl(assessmentId, 'xlsx')}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Download XLSX
          </a>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 rounded-lg border border-slate-200 bg-white p-4 text-sm sm:grid-cols-3">
        <div>
          <p className="text-slate-500">Total evidence links</p>
          <p className="font-semibold text-slate-900">{situation.total_evidence_links}</p>
        </div>
        <div>
          <p className="text-slate-500">Accepted / Edited</p>
          <p className="font-semibold text-slate-900">
            {situation.accepted_count} / {situation.edited_count}
          </p>
        </div>
        <div>
          <p className="text-slate-500">Rejected</p>
          <p className="font-semibold text-slate-900">{situation.rejected_count}</p>
        </div>
        <div>
          <p className="text-slate-500">Pending AI review</p>
          <p className="font-semibold text-slate-900">{situation.pending_ai_review_count}</p>
        </div>
        <div className="col-span-2 sm:col-span-3">
          <p className="text-slate-500">Unpopulated domains (no transcribed practices yet)</p>
          <p className="font-semibold text-slate-900">
            {situation.unpopulated_domains.length > 0 ? situation.unpopulated_domains.join(', ') : 'None'}
          </p>
        </div>
      </div>

      <div>
        <h2 className="font-semibold text-slate-900">Overall</h2>
        <div className="mt-2">
          <ScoreHeadline overall={overall} />
        </div>
      </div>

      <div>
        <h2 className="font-semibold text-slate-900">Complication — where gaps remain</h2>
        {complication.length === 0 ? (
          <p className="mt-2 text-sm text-slate-500">No gaps in any populated domain.</p>
        ) : (
          <div className="mt-2 space-y-3">
            {complication.map((group) => (
              <GapGroup key={group.domain_short_code} group={group} />
            ))}
          </div>
        )}
      </div>

      <div>
        <h2 className="font-semibold text-slate-900">Resolution — prioritized next steps</h2>
        <div className="mt-2">
          <ResolutionList items={resolution} />
        </div>
      </div>
    </div>
  )
}
