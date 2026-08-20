import type { Situation } from '../api/types'

// The second dashboard visual (ADR-0068). The Situation panel was five
// bare integers, including the one that decides how far the rest of the
// report can be trusted: how much evidence is still unreviewed.
//
// Drawn from counts the server already sends, as segments of
// total_evidence_links. The four statuses sum to that total by
// construction and a backend test pins it, so this bar is exact rather
// than approximate — no denominator is re-derived here, unlike the
// domain chart (ADR-0066) whose applicable-practice denominator is real
// domain logic and stays server-side.
//
// Rejected is deliberately NOT painted as a failure colour. Retrieval
// precision was measured at 0.012, so rejecting an AI proposal is the
// expected outcome for most of the queue, and a red bar would report
// healthy review work as something going wrong.

type Segment = {
  key: string
  label: string
  count: number
  className: string
  description: string
}

export default function ReviewProgressBar({ situation }: { situation: Situation }) {
  const total = situation.total_evidence_links

  if (total === 0) {
    return (
      <p className="text-sm text-slate-500">
        No evidence linked yet, so there is no review progress to show.
      </p>
    )
  }

  const segments: Segment[] = [
    {
      key: 'accepted',
      label: 'Accepted',
      count: situation.accepted_count,
      className: 'bg-emerald-500',
      description: 'counts toward the score',
    },
    {
      key: 'edited',
      label: 'Edited',
      count: situation.edited_count,
      className: 'bg-sky-500',
      description: 'corrected by a reviewer, then counted',
    },
    {
      key: 'rejected',
      label: 'Rejected',
      count: situation.rejected_count,
      className: 'bg-slate-400',
      description: 'declined; the practice stays a gap',
    },
    {
      key: 'pending',
      label: 'Awaiting review',
      count: situation.pending_ai_review_count,
      className: 'bg-amber-500',
      description: 'blocks finalization until decided',
    },
  ]

  // If the segments ever stop accounting for every link — a fifth review
  // status added without a segment here — show the remainder rather than
  // a bar that quietly stops short of full. A visibly odd bar is a much
  // better failure than a confidently wrong one.
  const accounted = segments.reduce((sum, segment) => sum + segment.count, 0)
  const unaccounted = total - accounted

  const shown = unaccounted > 0
    ? [
        ...segments,
        {
          key: 'other',
          label: 'Other',
          count: unaccounted,
          className: 'bg-fuchsia-500',
          description: 'in a review state this dashboard does not know',
        },
      ]
    : segments

  const pendingShare = Math.round((situation.pending_ai_review_count / total) * 100)

  return (
    <div>
      <div
        className="flex h-3 w-full overflow-hidden rounded-full bg-slate-200"
        role="img"
        aria-label={shown
          .filter((segment) => segment.count > 0)
          .map((segment) => `${segment.label}: ${segment.count} of ${total}`)
          .join(', ')}
      >
        {shown
          .filter((segment) => segment.count > 0)
          .map((segment) => (
            <div
              key={segment.key}
              className={segment.className}
              style={{ width: `${(segment.count / total) * 100}%` }}
            />
          ))}
      </div>

      <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
        {shown.map((segment) => (
          <li key={segment.key} className="flex items-center gap-1.5 text-xs text-slate-600">
            <span className={`h-2 w-2 rounded-full ${segment.className}`} aria-hidden="true" />
            <span className="font-medium text-slate-800">{segment.count}</span>
            <span>{segment.label}</span>
            <span className="text-slate-400">— {segment.description}</span>
          </li>
        ))}
      </ul>

      {/*
        The one number that changes what the rest of the report is worth
        (ADR-0058: pending review blocks finalization). Stated rather than
        left to be inferred from a bar segment.
      */}
      {situation.pending_ai_review_count > 0 && (
        <p className="mt-2 text-xs text-amber-700">
          {pendingShare}% of linked evidence is still awaiting a human decision, so scores below are
          provisional and this assessment cannot be finalized yet.
        </p>
      )}
    </div>
  )
}
