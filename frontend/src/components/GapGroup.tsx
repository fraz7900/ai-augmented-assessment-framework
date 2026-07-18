import type { DomainGapGroup } from '../api/types'

// executive-reporting skill: "every number needs a so-what" — total_practices
// and met_practices never render without the server-computed so_what
// sentence that connects them to a business consequence (ADR-0012).
export default function GapGroup({ group }: { group: DomainGapGroup }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex items-baseline justify-between">
        <h3 className="font-semibold text-slate-900">
          {group.domain_full_name} <span className="text-slate-400">({group.domain_short_code})</span>
        </h3>
        <span className="text-sm text-slate-500">
          {group.met_practices} of {group.total_practices} met
        </span>
      </div>
      <p className="mt-1 text-sm text-slate-600">{group.so_what}</p>
      {group.gaps.length > 0 && (
        <ul className="mt-3 space-y-1">
          {group.gaps.map((gap) => (
            <li key={gap.practice_id} className="flex items-center gap-2 text-sm">
              <span className="font-mono text-xs text-slate-500">{gap.practice_id}</span>
              <span className="text-slate-700">{gap.practice_text}</span>
              {gap.has_pending_ai_proposal && (
                <span className="rounded-full bg-purple-100 px-2 py-0.5 text-xs font-medium text-purple-800">
                  AI proposal pending review
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
