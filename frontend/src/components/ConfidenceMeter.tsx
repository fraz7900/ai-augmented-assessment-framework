// R-16/R-23: retrieval similarity has a real, disclosed precision ceiling
// near the threshold — the raw number is always shown, never collapsed
// into a hidden pass/fail badge. `label` distinguishes the two call sites
// (mapping "confidence" vs. chat "similarity") since neither is a
// calibrated probability (see models/assessment.py, models/chat.py).
export default function ConfidenceMeter({
  value,
  label = 'similarity',
}: {
  value: number
  label?: string
}) {
  const percent = Math.round(value * 100)
  return (
    <span className="inline-flex items-center gap-2" title={`Retrieval ${label} score, not a calibrated probability`}>
      <span className="h-1.5 w-16 overflow-hidden rounded-full bg-slate-200">
        <span className="block h-full rounded-full bg-indigo-500" style={{ width: `${percent}%` }} />
      </span>
      <span className="text-xs text-slate-500">
        {label} {percent}%
      </span>
    </span>
  )
}
