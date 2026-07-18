import type { EvidenceReviewStatus, EvidenceSource } from '../api/types'

// NFR-4: "Every AI-proposed evidence mapping must be distinguishable from a
// human-confirmed one in both data model and UI." This is the UI half of
// that requirement — every place an EvidenceLink is rendered must show
// this badge, never a bare practice_reference/document_id pair.
//
// executive-reporting skill: "Any executive report must visibly indicate
// which findings were human-reviewed and finalized versus still AI-proposed
// and pending review" — the same rule, applied here to the evidence list
// itself rather than just the dashboard.

const reviewStyles: Record<EvidenceReviewStatus, string> = {
  pending: 'bg-purple-100 text-purple-800',
  accepted: 'bg-emerald-100 text-emerald-800',
  edited: 'bg-blue-100 text-blue-800',
  rejected: 'bg-red-100 text-red-800',
}

const reviewLabels: Record<EvidenceReviewStatus, string> = {
  pending: 'Pending review',
  accepted: 'Accepted',
  edited: 'Edited',
  rejected: 'Rejected',
}

export default function EvidenceSourceBadge({
  source,
  reviewStatus,
}: {
  source: EvidenceSource
  reviewStatus: EvidenceReviewStatus
}) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
          source === 'ai_proposed' ? 'bg-indigo-100 text-indigo-800' : 'bg-slate-200 text-slate-700'
        }`}
      >
        {source === 'ai_proposed' ? 'AI-proposed' : 'Manual'}
      </span>
      <span
        className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${reviewStyles[reviewStatus]}`}
      >
        {reviewLabels[reviewStatus]}
      </span>
    </span>
  )
}
