import type { OverallSummary } from '../api/types'

// R-15: a cumulative_mil score (whole-number MIL 0-3) and a coverage score
// (0.0-1.0 fraction) mean different things and must never be blended into
// one fabricated number. `overall.headline` is already the server-computed,
// scoring-model-aware sentence (ADR-0012) — this component renders it
// verbatim plus its one supporting stat, never re-deriving or averaging
// anything client-side.
export default function ScoreHeadline({ overall }: { overall: OverallSummary }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <p className="text-lg font-semibold text-slate-900">{overall.headline}</p>
      <p className="mt-1 text-sm text-slate-500">
        {overall.populated_domains} of {overall.total_domains} domains populated with transcribed
        practices
        {overall.scoring_model === 'cumulative_mil' && overall.domains_at_mil1_or_above != null && (
          <> · {overall.domains_at_mil1_or_above} domain(s) at MIL1 or above</>
        )}
        {overall.scoring_model === 'coverage' && overall.overall_coverage_fraction != null && (
          <> · {(overall.overall_coverage_fraction * 100).toFixed(0)}% overall coverage</>
        )}
      </p>
    </div>
  )
}
