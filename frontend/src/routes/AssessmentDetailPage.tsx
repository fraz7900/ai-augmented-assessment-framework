import { NavLink, Outlet, useParams } from 'react-router-dom'
import { useAssessment } from '../api/assessments'
import StatusBadge from '../components/StatusBadge'
import type { Assessment } from '../api/types'

export type AssessmentTabContext = {
  assessmentId: string
  assessment: Assessment
}

const tabLinkClass = ({ isActive }: { isActive: boolean }) =>
  `border-b-2 px-3 py-2 text-sm font-medium ${
    isActive ? 'border-slate-900 text-slate-900' : 'border-transparent text-slate-500 hover:text-slate-700'
  }`

export default function AssessmentDetailPage() {
  const { assessmentId } = useParams<{ assessmentId: string }>()
  const { data: assessment, isLoading, isError, error } = useAssessment(assessmentId)

  if (isLoading) return <p className="text-sm text-slate-500">Loading…</p>
  if (isError) return <p className="text-sm text-red-700">{error.message}</p>
  if (!assessment || !assessmentId) return null

  return (
    <div>
      <div className="flex items-center gap-3">
        <h1 className="text-xl font-semibold text-slate-900">{assessment.name}</h1>
        <StatusBadge status={assessment.status} />
      </div>
      <p className="text-sm text-slate-500">{assessment.framework_name}</p>

      <nav className="mt-4 flex gap-1 border-b border-slate-200">
        <NavLink to="overview" className={tabLinkClass}>
          Overview
        </NavLink>
        <NavLink to="evidence" className={tabLinkClass}>
          Evidence
        </NavLink>
        <NavLink to="dashboard" className={tabLinkClass}>
          Dashboard
        </NavLink>
        <NavLink to="chat" className={tabLinkClass}>
          Chat
        </NavLink>
      </nav>

      <div className="mt-4">
        <Outlet context={{ assessmentId, assessment } satisfies AssessmentTabContext} />
      </div>
    </div>
  )
}
