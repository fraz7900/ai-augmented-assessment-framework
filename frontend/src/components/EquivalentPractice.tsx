import ConfidenceMeter from './ConfidenceMeter'
import type { Equivalent } from '../api/types'

// US-5.2/FR-14 (ADR-0019): each entry here is a deliberately-reviewed,
// human-curated cross-framework equivalence, not an automatic
// similarity-threshold match (.claude/skills/framework-mapping/SKILL.md
// point 3) — the rationale is always shown alongside the similarity
// score, never the score alone, so a reader sees *why* two practices
// from different frameworks were judged equivalent, not just a number.
export default function EquivalentPractice({ equivalent }: { equivalent: Equivalent }) {
  return (
    <div className="rounded-md border border-indigo-100 bg-indigo-50/50 p-2 text-xs">
      <div className="flex items-center justify-between gap-2">
        <span className="font-medium text-indigo-900">
          Also satisfies {equivalent.framework_name}: <span className="font-mono">{equivalent.practice_id}</span>
        </span>
        <ConfidenceMeter value={equivalent.similarity} label="similarity" />
      </div>
      <p className="mt-1 text-slate-700">{equivalent.practice_text}</p>
      <p className="mt-1 italic text-slate-500">{equivalent.rationale}</p>
    </div>
  )
}
