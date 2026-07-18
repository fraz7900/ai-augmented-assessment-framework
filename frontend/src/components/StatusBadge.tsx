import type { AssessmentStatus } from '../api/types'

const styles: Record<AssessmentStatus, string> = {
  draft: 'bg-slate-100 text-slate-700',
  in_review: 'bg-amber-100 text-amber-800',
  finalized: 'bg-emerald-100 text-emerald-800',
}

const labels: Record<AssessmentStatus, string> = {
  draft: 'Draft',
  in_review: 'In review',
  finalized: 'Finalized',
}

export default function StatusBadge({ status }: { status: AssessmentStatus }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${styles[status]}`}>
      {labels[status]}
    </span>
  )
}
