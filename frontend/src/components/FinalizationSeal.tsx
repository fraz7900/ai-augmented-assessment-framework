import { AlertTriangle, CheckCircle2, HelpCircle, Loader2, ShieldCheck } from 'lucide-react'
import type { SealVerification, SealVerificationStatus } from '../api/types'

interface Props {
  seal: string | null | undefined
  verification: SealVerification | undefined
  isVerifying: boolean
  error: Error | null
  onVerify: () => void
}

const verdicts: Record<
  SealVerificationStatus,
  { tone: 'ok' | 'warn' | 'error' | 'neutral'; heading: string }
> = {
  verified: { tone: 'ok', heading: 'Unaltered since finalization' },
  altered: { tone: 'error', heading: 'This record has changed since it was finalized' },
  // Not a failure. An assessment finalized before sealing existed is
  // unverified, which is a different thing from untrustworthy — and
  // showing it in red would say otherwise.
  unsealed: { tone: 'neutral', heading: 'No seal to check against' },
  unverifiable: { tone: 'warn', heading: 'This build cannot check that seal' },
}

const toneClasses: Record<'ok' | 'warn' | 'error' | 'neutral', string> = {
  ok: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  warn: 'border-amber-200 bg-amber-50 text-amber-800',
  error: 'border-red-200 bg-red-50 text-red-800',
  neutral: 'border-slate-200 bg-slate-50 text-slate-700',
}

function VerdictIcon({ tone }: { tone: 'ok' | 'warn' | 'error' | 'neutral' }) {
  if (tone === 'ok') return <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
  if (tone === 'neutral') return <HelpCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
  return <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
}

/**
 * The finalization seal, and the button that checks it (ADR-0060).
 *
 * The seal is a SHA-256 over the whole finalized record, written when
 * the assessment was frozen. Its value here is not decorative: it is
 * printed into every PDF and XLSX export, so a reader holding an older
 * report can compare the two. That comparison is the actual
 * tamper-evidence — a digest kept only beside the record it protects
 * proves nothing against someone who edits the record and recomputes
 * the digest.
 *
 * Shown only for a finalized assessment. Before that there is nothing
 * to seal, and offering the control anyway would suggest a draft is
 * supposed to be immutable.
 */
export default function FinalizationSeal({
  seal,
  verification,
  isVerifying,
  error,
  onVerify,
}: Props) {
  const verdict = verification ? verdicts[verification.status] : null

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="flex items-center gap-2 font-semibold text-slate-900">
        <ShieldCheck className="h-4 w-4 text-slate-400" aria-hidden="true" />
        Finalization seal
      </h2>

      {!seal ? (
        <p className="mt-2 text-sm text-slate-600">
          This assessment was finalized before sealing existed, so there is no digest to check it
          against. It is deliberately not sealed now — a seal written today would only attest that
          the record has not changed since today.
        </p>
      ) : (
        <>
          <p className="mt-2 text-sm text-slate-600">
            A digest of this record as it was when frozen. The same value is printed on every
            exported report, so a reader holding an older copy can check it against this one.
          </p>
          <p className="mt-2 select-all break-all rounded bg-slate-50 p-2 font-mono text-[11px] text-slate-600">
            {seal}
          </p>
        </>
      )}

      <div className="mt-3 flex items-center gap-3">
        <button
          type="button"
          onClick={onVerify}
          disabled={isVerifying}
          className="inline-flex items-center gap-2 rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-800 enabled:hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isVerifying && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
          {isVerifying ? 'Checking…' : 'Check this record against its seal'}
        </button>
        {!verification && !isVerifying && (
          <span className="text-sm text-slate-500">Recomputes the digest from stored data</span>
        )}
      </div>

      {error && (
        <p className="mt-3 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          {error.message}
        </p>
      )}

      {verification && verdict && (
        <div className={`mt-3 flex items-start gap-2 rounded-md border p-3 text-sm ${toneClasses[verdict.tone]}`}>
          <VerdictIcon tone={verdict.tone} />
          <div>
            <p className="font-medium">{verdict.heading}</p>
            <p className="mt-1">{verification.detail}</p>
            {/*
              Both digests, shown only when they disagree. Side by side
              they turn "the app says something is wrong" into something
              a person can carry to whoever else holds a copy.
            */}
            {verification.status === 'altered' && (
              <dl className="mt-2 space-y-1 font-mono text-[11px]">
                <div>
                  <dt className="inline font-sans font-medium">Sealed: </dt>
                  <dd className="inline break-all">{verification.sealed_digest}</dd>
                </div>
                <div>
                  <dt className="inline font-sans font-medium">Now: </dt>
                  <dd className="inline break-all">{verification.computed_digest}</dd>
                </div>
              </dl>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
