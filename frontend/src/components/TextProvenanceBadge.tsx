import type { TextProvenance } from '../api/types'

// R-33, open since Sprint 19 (ADR-0074): OCR-recovered text is
// approximate, this product's credibility rests on verbatim quotation,
// and until now nothing downstream of ingestion could tell a reviewer
// which passages were which. The parse status was shown at upload and
// then lost by the time anyone read a quote.
//
// Four answers, not two. "This passage is approximate", "OCR ran
// somewhere in this document and I cannot say about this passage", and
// "I have no basis for an answer" are genuinely different, and
// collapsing any pair of them either invents a warning or hides one.
//
// `exact` renders nothing at all. A badge on every ordinary quotation
// would be noise, and noise is what makes people stop reading the badge
// that matters.

const PRESENTATION: Record<
  Exclude<TextProvenance, 'exact'>,
  { label: string; title: string; className: string }
> = {
  ocr: {
    label: 'OCR — approximate',
    title:
      'This passage was recovered by local OCR from a page with no text layer. Check it against the source page before relying on the exact wording.',
    className: 'bg-amber-50 text-amber-800 ring-amber-200',
  },
  possibly_ocr: {
    label: 'may be OCR',
    title:
      'OCR was used somewhere in this document, but which page this passage came from was not recorded — it predates per-page provenance. Treat the wording as unverified.',
    className: 'bg-amber-50 text-amber-700 ring-amber-200',
  },
  unknown: {
    label: 'provenance unrecorded',
    title:
      'This document has no recorded parse status, so whether its text was read or recognised is unknown. Absence of a record is not evidence of an intact text layer.',
    className: 'bg-slate-100 text-slate-600 ring-slate-200',
  },
}

export default function TextProvenanceBadge({ provenance }: { provenance: TextProvenance }) {
  if (provenance === 'exact') return null
  const presentation = PRESENTATION[provenance]
  if (!presentation) return null

  return (
    <span
      title={presentation.title}
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${presentation.className}`}
    >
      {presentation.label}
    </span>
  )
}
