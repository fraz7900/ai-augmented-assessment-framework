import type { PracticeFindingStatus } from '../api/types'

// ADR-0030: the whole point of this badge is that a gap's status is no
// longer an undifferentiated "unmet practice" — a reviewer who has
// explicitly examined this and confirmed it's not met (not_satisfied)
// reads differently from a practice nobody has looked at yet
// (insufficient_evidence, the default with no PracticeFinding at all).
const styles: Record<PracticeFindingStatus, string> = {
  satisfied: 'bg-emerald-100 text-emerald-800',
  partially_satisfied: 'bg-amber-100 text-amber-800',
  not_satisfied: 'bg-red-100 text-red-800',
  insufficient_evidence: 'bg-slate-100 text-slate-600',
  not_applicable: 'bg-slate-100 text-slate-500',
}

const labels: Record<PracticeFindingStatus, string> = {
  satisfied: 'Satisfied',
  partially_satisfied: 'Partially satisfied',
  not_satisfied: 'Not satisfied',
  insufficient_evidence: 'No finding yet',
  not_applicable: 'Not applicable',
}

export default function PracticeFindingStatusBadge({ status }: { status: PracticeFindingStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${styles[status]}`}
    >
      {labels[status]}
    </span>
  )
}
