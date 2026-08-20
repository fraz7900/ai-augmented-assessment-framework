import type { DomainProgress, OverallSummary } from '../api/types'

// Domain completion, as bars (ADR-0066). A tester asked for visuals on a
// dashboard that was all text and numbers, a domain completion bar chart
// specifically.
//
// The bar length is met/total APPLICABLE practices, computed server-side,
// because that ratio means the same thing under both scoring models.
// `domain_scores` deliberately is NOT the bar: it is an ordinal MIL (0-3)
// under cumulative_mil and a fraction under coverage, and drawing both as
// bar length would put a maturity level and a percentage on one axis —
// the blend R-15 forbids and the reason OverallSummary refuses to average
// domain scores at all.
//
// Under cumulative_mil the bar and the score are different shapes, and
// the chart has to say so out loud: MIL is gated, so 9 of 10 practices
// met is 90% complete and still MIL0 when one MIL1 practice is missing.
// Without the gate label a reader concludes the product is broken; with
// it, they learn what to do next.
//
// Rendered as plain elements rather than a charting library. Ten bars do
// not justify a dependency, and this repo's one peer-conflict story
// (ADR-0016) is enough.

function scoreLabel(entry: DomainProgress, scoringModel: string): string {
  if (scoringModel === 'cumulative_mil') return `MIL${entry.score.toFixed(0)}`
  return `${Math.round(entry.score * 100)}% coverage`
}

export default function DomainCompletionChart({
  progress,
  overall,
}: {
  progress: DomainProgress[]
  overall: OverallSummary
}) {
  if (progress.length === 0) {
    return (
      <p className="text-sm text-slate-500">
        No domain has transcribed practices yet, so there is nothing to chart.
      </p>
    )
  }

  // Worst first: the chart is read to decide where to work next, and the
  // domain with the most missing practices is that answer. Ties break on
  // short code so the order is stable between renders.
  const ordered = [...progress].sort((a, b) => {
    const aMissing = a.total_practices - a.met_practices
    const bMissing = b.total_practices - b.met_practices
    return bMissing - aMissing || a.short_code.localeCompare(b.short_code)
  })

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <ul className="space-y-3">
        {ordered.map((entry) => {
          const percent = Math.round((entry.met_practices / entry.total_practices) * 100)
          const isComplete = entry.met_practices === entry.total_practices
          return (
            <li key={entry.short_code}>
              <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
                <span className="text-sm text-slate-800">
                  <span className="font-mono text-xs text-slate-500">{entry.short_code}</span>{' '}
                  {entry.full_name}
                </span>
                <span className="text-xs text-slate-500">
                  {entry.met_practices} of {entry.total_practices} practices ·{' '}
                  <span className="font-medium text-slate-700">
                    {scoreLabel(entry, overall.scoring_model)}
                  </span>
                </span>
              </div>
              <div
                className="mt-1 h-2 w-full overflow-hidden rounded-full bg-slate-200"
                role="img"
                aria-label={`${entry.full_name}: ${entry.met_practices} of ${entry.total_practices} applicable practices met, scoring ${scoreLabel(entry, overall.scoring_model)}`}
              >
                <div
                  className={`h-full rounded-full ${isComplete ? 'bg-emerald-500' : 'bg-indigo-500'}`}
                  style={{ width: `${percent}%` }}
                />
              </div>
              {/*
                The reconciliation. A high bar next to MIL0 is not a
                contradiction and not a bug — it is what a gated scale
                does — but only if the chart says which gate and by how
                much.

                Rendered verbatim from the server rather than composed
                here (ADR-0069), the same way ScoreHeadline renders its
                sentence: the PDF and XLSX print this too, and an
                interpretation written separately in three renderers is
                three chances to say something different about the same
                number.
              */}
              {entry.gate_note && (
                <p className="mt-1 text-xs text-amber-700">{entry.gate_note}</p>
              )}
            </li>
          )
        })}
      </ul>

      <p className="mt-3 border-t border-slate-100 pt-3 text-xs text-slate-500">
        {overall.scoring_model === 'cumulative_mil' ? (
          <>
            Bars show applicable practices met. They are not the maturity score: MIL is cumulative,
            so a domain reaches MIL2 only when every MIL1 practice is also met. Practices marked not
            applicable are excluded from both.
          </>
        ) : (
          <>
            Bars show applicable practices met, which is the same measure as this framework's
            coverage score. Practices marked not applicable are excluded from both.
          </>
        )}
      </p>
    </div>
  )
}
