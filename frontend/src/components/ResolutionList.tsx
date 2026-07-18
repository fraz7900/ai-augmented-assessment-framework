import type { ResolutionItem } from '../api/types'

// Prioritization here is effort-based (fewest missing practices first),
// disclosed as such via `rationale` — never presented as a fabricated
// business-impact rank (R-19, ADR-0012). Rendered in the order the API
// returns it; not re-sorted client-side.
export default function ResolutionList({ items }: { items: ResolutionItem[] }) {
  if (items.length === 0) {
    return <p className="text-sm text-slate-500">No prioritized gaps — every populated domain is fully met.</p>
  }
  return (
    <ol className="space-y-2">
      {items.map((item, index) => (
        <li key={item.domain_short_code} className="rounded-lg border border-slate-200 bg-white p-4">
          <div className="flex items-baseline justify-between">
            <span className="font-semibold text-slate-900">
              {index + 1}. {item.domain_full_name}{' '}
              <span className="text-slate-400">({item.domain_short_code})</span>
            </span>
            <span className="text-sm text-slate-500">{item.missing_count} missing</span>
          </div>
          <p className="mt-1 text-sm text-slate-600">{item.rationale}</p>
        </li>
      ))}
    </ol>
  )
}
