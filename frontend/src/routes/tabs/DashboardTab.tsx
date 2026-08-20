import { useOutletContext } from 'react-router-dom'
import { Download, Info } from 'lucide-react'
import { reportUrl, useDashboard } from '../../api/assessments'
import ScoreHeadline from '../../components/ScoreHeadline'
import DomainCompletionChart from '../../components/DomainCompletionChart'
import ReviewProgressBar from '../../components/ReviewProgressBar'
import GapGroup from '../../components/GapGroup'
import ResolutionList from '../../components/ResolutionList'
import SanitizationPanel from '../../components/SanitizationPanel'
import type { AssessmentTabContext } from '../AssessmentDetailPage'

// executive-reporting skill: lead with situation/complication/resolution,
// not a raw score table (Marcus/CISO persona, US-6.1) — this renders
// DashboardReport's three sections verbatim, in that order, with no
// client-side re-derivation of any number.
export default function DashboardTab() {
  const { assessmentId, assessment } = useOutletContext<AssessmentTabContext>()
  const { data: dashboard, isLoading, isError, error } = useDashboard(assessmentId)
  const isFinalized = assessment.status === 'finalized'

  if (isLoading) return <p className="text-sm text-slate-500">Loading…</p>
  if (isError) return <p className="text-sm text-red-700">{error.message}</p>
  if (!dashboard) return null

  const { situation, overall, complication, resolution, domain_progress: domainProgress } =
    dashboard

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-semibold text-slate-900">Situation</h2>
        <div className="flex gap-2">
          <a
            href={reportUrl(assessmentId, 'pdf')}
            className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            <Download className="h-4 w-4" aria-hidden="true" />
            Download PDF
          </a>
          <a
            href={reportUrl(assessmentId, 'xlsx')}
            className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            <Download className="h-4 w-4" aria-hidden="true" />
            Download XLSX
          </a>
        </div>
      </div>

      <SanitizationPanel assessmentId={assessmentId} />

      <div className="rounded-lg border border-slate-200 bg-white p-4">
        {/*
          The shape of the review, before its five component integers
          (ADR-0068). How much evidence is still unreviewed is the number
          that decides how far everything below can be trusted, and it
          read as one figure among five.
        */}
        <ReviewProgressBar situation={situation} />
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

        {/*
          What those counts mean. executive-reporting.mdc requires every
          number in executive-facing output to carry a consequence, and
          this panel was five bare integers — including the two that
          decide how far the rest of the report can be trusted.

          Rendered from situation.so_what rather than composed here: the
          same sentences appear in the PDF and XLSX exports, so screen
          and document cannot drift into saying different things about
          the same figures.
        */}
        {situation.so_what.length > 0 && (
          <div className="col-span-2 border-t border-slate-100 pt-3 sm:col-span-3">
            <p className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-slate-500">
              <Info className="h-3.5 w-3.5" aria-hidden="true" />
              What this means
            </p>
            <ul className="mt-1.5 space-y-1.5">
              {situation.so_what.map((sentence) => (
                <li key={sentence} className="flex gap-2 text-sm text-slate-700">
                  <span aria-hidden="true" className="text-slate-300">
                    —
                  </span>
                  <span>{sentence}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <div>
        <h2 className="font-semibold text-slate-900">Overall</h2>
        <div className="mt-2">
          <ScoreHeadline overall={overall} />
        </div>
      </div>

      <div>
        <h2 className="font-semibold text-slate-900">Domain completion</h2>
        {/*
          Kept below the headline deliberately. ScoreHeadline renders the
          server's scoring-model-aware sentence verbatim, and that sentence
          is what the assessment actually claims; the chart is the shape of
          it. Putting bars first would make the picture the claim.
        */}
        <div className="mt-2">
          <DomainCompletionChart progress={domainProgress} overall={overall} />
        </div>
      </div>

      <div>
        <h2 className="font-semibold text-slate-900">Complication — where gaps remain</h2>
        {complication.length === 0 ? (
          <p className="mt-2 text-sm text-slate-500">No gaps in any populated domain.</p>
        ) : (
          <div className="mt-2 space-y-3">
            {complication.map((group) => (
              <GapGroup
                key={group.domain_short_code}
                group={group}
                assessmentId={assessmentId}
                isFinalized={isFinalized}
              />
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
