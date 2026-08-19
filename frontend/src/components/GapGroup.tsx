import {
  useEvidenceRequests,
  useRequestMoreEvidence,
  useResolveEvidenceRequest,
  useSetPracticeFinding,
} from '../api/assessments'
import type { DomainGapGroup } from '../api/types'
import PracticeFindingStatusBadge from './PracticeFindingStatusBadge'
import PracticeFindingControls from './PracticeFindingControls'
import EvidenceRequestControls from './EvidenceRequestControls'
import EvidenceRequestBadge from './EvidenceRequestBadge'
import CitedEvidenceList from './CitedEvidenceList'

// executive-reporting skill: "every number needs a so-what" — total_practices
// and met_practices never render without the server-computed so_what
// sentence that connects them to a business consequence (ADR-0012).
export default function GapGroup({
  group,
  assessmentId,
  isFinalized,
}: {
  group: DomainGapGroup
  assessmentId: string
  isFinalized: boolean
}) {
  const setFinding = useSetPracticeFinding(assessmentId)
  const { data: evidenceRequests } = useEvidenceRequests(assessmentId)
  const requestMoreEvidence = useRequestMoreEvidence(assessmentId)
  const resolveEvidenceRequest = useResolveEvidenceRequest(assessmentId)

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
        <ul className="mt-3 space-y-2">
          {group.gaps.map((gap) => (
            <li key={gap.practice_id} className="border-t border-slate-100 pt-2 first:border-t-0 first:pt-0">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className="font-mono text-xs text-slate-500">{gap.practice_id}</span>
                <span className="text-slate-700">{gap.practice_text}</span>
                <PracticeFindingStatusBadge status={gap.status} />
                {gap.has_pending_ai_proposal && (
                  <span className="rounded-full bg-purple-100 px-2 py-0.5 text-xs font-medium text-purple-800">
                    AI proposal pending review
                  </span>
                )}
              </div>
              {gap.finding_rationale && (
                <p className="mt-1 text-xs text-slate-500">{gap.finding_rationale}</p>
              )}
              <CitedEvidenceList citations={gap.cited_evidence} />
              {evidenceRequests
                ?.filter((r) => r.practice_reference === gap.practice_id && !r.resolved_at)
                .map((request) => (
                  <EvidenceRequestBadge
                    key={request.id}
                    request={request}
                    isDisabled={isFinalized}
                    isSubmitting={resolveEvidenceRequest.isPending}
                    onResolve={() => {
                      // request.id is typed optional only because the backend
                      // schema marks it as having a server-side default
                      // (SQLModel's default_factory) -- every real response
                      // always has one; this guard is defensive, not
                      // expected to ever actually trigger.
                      if (!request.id) return
                      resolveEvidenceRequest.mutate({ requestId: request.id })
                    }}
                  />
                ))}
              <div className="mt-2 flex flex-wrap items-center gap-3">
                <PracticeFindingControls
                  isDisabled={isFinalized}
                  isSubmitting={setFinding.isPending}
                  onSubmit={(status, rationale) =>
                    setFinding.mutate({ practiceReference: gap.practice_id, status, rationale })
                  }
                />
                <EvidenceRequestControls
                  isDisabled={isFinalized}
                  isSubmitting={requestMoreEvidence.isPending}
                  onSubmit={(note) =>
                    requestMoreEvidence.mutate({ practiceReference: gap.practice_id, note })
                  }
                />
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
