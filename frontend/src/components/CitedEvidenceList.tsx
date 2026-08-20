import type { EvidenceCitation } from '../api/types'
import { reviewLabels, reviewStyles } from './EvidenceSourceBadge'
import TextProvenanceBadge from './TextProvenanceBadge'

// ADR-0040 computed GapItem.cited_evidence server-side but nothing in the
// Dashboard tab ever rendered it -- this is that rendering, closing the
// gap disclosed in ADR-0040/ADR-0050. IDs and review status only, never
// evidence text, matching EvidenceCitation's own docstring (the backend
// model deliberately excludes raw evidence content from this shape).
//
// is_superseded (ADR-0050) is read directly from the citation the
// dashboard already computed it into -- no extra per-document API call
// here, unlike EvidenceTab.tsx's SupersededDocumentBadge (EvidenceLink
// itself doesn't carry is_superseded, so that screen has to look it up
// live per document).
export default function CitedEvidenceList({ citations }: { citations: EvidenceCitation[] }) {
  if (citations.length === 0) return null
  return (
    <ul className="mt-1 space-y-0.5">
      {citations.map((citation) => (
        <li key={citation.evidence_link_id} className="flex flex-wrap items-center gap-1.5 text-xs">
          <span className="font-mono text-slate-500">{citation.document_id}</span>
          <span
            className={`inline-flex items-center rounded-full px-2 py-0.5 font-medium ${reviewStyles[citation.review_status]}`}
          >
            {reviewLabels[citation.review_status]}
          </span>
          {/* Where this evidence's text came from (ADR-0076). Read off
              the citation the dashboard already resolved it into, per
              chunk where the link names one — same no-extra-call shape
              as is_superseded above, and the same badge the chat tab
              uses so screen and export say one thing. */}
          <TextProvenanceBadge provenance={citation.text_provenance} />
          {citation.is_superseded && (
            <span className="inline-flex items-center rounded-full bg-amber-100 px-2 py-0.5 font-medium text-amber-800">
              ⚠ document superseded
            </span>
          )}
        </li>
      ))}
    </ul>
  )
}
