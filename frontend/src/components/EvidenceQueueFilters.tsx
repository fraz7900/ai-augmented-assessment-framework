import type { EvidenceFilters } from '../api/assessments'
import type { EvidenceQueueSummary, EvidenceReviewStatus } from '../api/types'

// The review queue is unfilterable today: GET /evidence returns every
// link, and a real assessment can hold hundreds (ADR-0065). This control
// narrows what a reviewer READS. It deliberately offers no way to act on
// the narrowed set — a filter that ends in one button applying a decision
// to rows nobody opened is the auto-accept AGENTS.md rule 2 forbids,
// wearing a different name.
//
// Every count shown here comes from the summary endpoint, which is
// computed over the whole queue and never over the filtered view. That is
// the property that stops this control from lying: a reviewer always sees
// what they are NOT looking at.

const STATUSES: { value: EvidenceReviewStatus; label: string }[] = [
  { value: 'pending', label: 'Awaiting review' },
  { value: 'accepted', label: 'Accepted' },
  { value: 'edited', label: 'Edited' },
  { value: 'rejected', label: 'Rejected' },
]

// Bands, not a free number. R-16 measured correct practice/evidence pairs
// at 0.65–0.78 and a confirmed false positive at 0.71, so a box inviting
// someone to type 0.85 would invite a cutoff above everything ever
// observed to be correct. These labels say what each band is worth.
const CONFIDENCE_BANDS: { id: string; label: string; min?: number; max?: number }[] = [
  { id: 'any', label: 'Any confidence' },
  { id: 'weak', label: 'Below the threshold band (< 0.55)', max: 0.55 },
  { id: 'borderline', label: 'Borderline (0.55–0.65)', min: 0.55, max: 0.65 },
  { id: 'measured', label: 'Measured-correct band (0.65–0.78)', min: 0.65, max: 0.78 },
  { id: 'unmeasured', label: 'Above any measured match (> 0.78)', min: 0.78 },
]

const selectClass =
  'mt-1 w-full rounded-md border border-slate-300 bg-white px-2 py-1 text-sm text-slate-900'

export default function EvidenceQueueFilters({
  filters,
  summary,
  shownCount,
  onChange,
}: {
  filters: EvidenceFilters
  summary: EvidenceQueueSummary | undefined
  shownCount: number
  onChange: (next: EvidenceFilters) => void
}) {
  const activeBand =
    CONFIDENCE_BANDS.find(
      (band) => band.min === filters.min_confidence && band.max === filters.max_confidence,
    ) ?? CONFIDENCE_BANDS[0]

  const isFiltered =
    filters.review_status != null ||
    (filters.domain != null && filters.domain !== '') ||
    filters.min_confidence != null ||
    filters.max_confidence != null

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4" aria-label="Filter the review queue">
      <div className="grid gap-3 sm:grid-cols-3">
        <div>
          <label className="block text-xs font-medium text-slate-700" htmlFor="filter-status">
            Review state
          </label>
          <select
            id="filter-status"
            className={selectClass}
            value={filters.review_status ?? ''}
            onChange={(event) =>
              onChange({
                ...filters,
                review_status: (event.target.value || undefined) as EvidenceReviewStatus | undefined,
              })
            }
          >
            <option value="">All states</option>
            {STATUSES.map((status) => (
              <option key={status.value} value={status.value}>
                {status.label}
                {summary ? ` (${summary.by_status[status.value] ?? 0})` : ''}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-700" htmlFor="filter-domain">
            Domain
          </label>
          <select
            id="filter-domain"
            className={selectClass}
            value={filters.domain ?? ''}
            onChange={(event) => onChange({ ...filters, domain: event.target.value || undefined })}
          >
            {/* Only domains with links in them are offered — the server
                omits empty ones, so a ten-domain framework does not
                produce a chooser of seven dead entries. */}
            <option value="">All domains</option>
            {(summary?.by_domain ?? []).map((domain) => (
              <option key={domain.short_code} value={domain.short_code}>
                {domain.short_code} · {domain.full_name} ({domain.pending} of {domain.total} awaiting)
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-700" htmlFor="filter-confidence">
            Retrieval confidence
          </label>
          <select
            id="filter-confidence"
            className={selectClass}
            value={activeBand.id}
            onChange={(event) => {
              const band = CONFIDENCE_BANDS.find((candidate) => candidate.id === event.target.value)
              onChange({ ...filters, min_confidence: band?.min, max_confidence: band?.max })
            }}
          >
            {CONFIDENCE_BANDS.map((band) => (
              <option key={band.id} value={band.id}>
                {band.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
        <span>
          Showing <span className="font-medium text-slate-700">{shownCount}</span>
          {summary ? ` of ${summary.total}` : ''} link(s)
        </span>

        {isFiltered && (
          <button
            type="button"
            onClick={() => onChange({})}
            className="font-medium text-indigo-600 underline underline-offset-2 hover:text-indigo-500"
          >
            Clear filters
          </button>
        )}

        {/* The disclosure that keeps the domain filter honest. These
            links belong to no domain, so no domain filter can reach
            them — a reviewer working domain by domain would otherwise
            never learn they exist. */}
        {summary != null && summary.unmapped > 0 && (
          <span className="text-amber-700">
            {summary.unmapped} link(s) cite a practice outside this framework version and appear
            under no domain.
          </span>
        )}
      </div>

      {filters.min_confidence != null && filters.min_confidence >= 0.78 && (
        <p className="mt-2 text-xs text-amber-700">
          No correct match has been measured above 0.78 (R-16). A high score here is not evidence
          that a link is right — it is a band nobody has calibrated.
        </p>
      )}
    </section>
  )
}
