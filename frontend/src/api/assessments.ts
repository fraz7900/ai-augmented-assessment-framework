import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { API_BASE_URL, apiClient } from './client'
import type {
  Assessment,
  AssessmentStatusChange,
  ChatResponse,
  CreateAssessmentRequest,
  DashboardReport,
  EvidenceLink,
  EvidenceRequest,
  FinalizationReadiness,
  SealVerification,
  LinkEvidenceRequest,
  PracticeFinding,
  PracticeFindingChange,
  PracticeFindingStatus,
  ReviewEvidenceRequest,
  SanitizationApproval,
  SanitizationPreview,
  StatusTransitionRequest,
} from './types'

const keys = {
  assessments: ['assessments'] as const,
  assessment: (id: string) => ['assessments', id] as const,
  statusHistory: (id: string) => ['assessments', id, 'status-history'] as const,
  evidence: (id: string) => ['assessments', id, 'evidence'] as const,
  dashboard: (id: string) => ['assessments', id, 'dashboard'] as const,
  practiceFindings: (id: string) => ['assessments', id, 'practice-findings'] as const,
  practiceFindingHistory: (id: string, practiceReference: string) =>
    ['assessments', id, 'practice-findings', practiceReference, 'history'] as const,
  evidenceRequests: (id: string) => ['assessments', id, 'evidence-requests'] as const,
  finalizationReadiness: (id: string) =>
    ['assessments', id, 'finalization-readiness'] as const,
  sealVerification: (id: string) => ['assessments', id, 'seal-verification'] as const,
}

export function useAssessments() {
  return useQuery({
    queryKey: keys.assessments,
    queryFn: () => apiClient.get<Assessment[]>('/assessments'),
  })
}

export function useAssessment(id: string | undefined) {
  return useQuery({
    queryKey: keys.assessment(id ?? ''),
    queryFn: () => apiClient.get<Assessment>(`/assessments/${id}`),
    enabled: !!id,
  })
}

export function useCreateAssessment() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: CreateAssessmentRequest) => apiClient.post<Assessment>('/assessments', body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.assessments }),
  })
}

export function useStatusHistory(assessmentId: string | undefined) {
  return useQuery({
    queryKey: keys.statusHistory(assessmentId ?? ''),
    queryFn: () =>
      apiClient.get<AssessmentStatusChange[]>(`/assessments/${assessmentId}/status-history`),
    enabled: !!assessmentId,
  })
}

export function useTransitionStatus(assessmentId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: StatusTransitionRequest) =>
      apiClient.post<Assessment>(`/assessments/${assessmentId}/status`, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.assessment(assessmentId) })
      queryClient.invalidateQueries({ queryKey: keys.statusHistory(assessmentId) })
      queryClient.invalidateQueries({ queryKey: keys.assessments })
    },
  })
}

export function useEvidenceLinks(assessmentId: string | undefined) {
  return useQuery({
    queryKey: keys.evidence(assessmentId ?? ''),
    queryFn: () => apiClient.get<EvidenceLink[]>(`/assessments/${assessmentId}/evidence`),
    enabled: !!assessmentId,
  })
}

export function useLinkEvidence(assessmentId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: LinkEvidenceRequest) =>
      apiClient.post<EvidenceLink>(`/assessments/${assessmentId}/evidence`, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.evidence(assessmentId) }),
  })
}

export function useProposeMappings(assessmentId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => apiClient.post<EvidenceLink[]>(`/assessments/${assessmentId}/propose-mappings`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.evidence(assessmentId) })
      // New AI proposals are unreviewed by definition, so proposing
      // mappings BLOCKS finalization until they are reviewed.
      queryClient.invalidateQueries({ queryKey: keys.finalizationReadiness(assessmentId) })
    },
  })
}

export function useReviewEvidence(assessmentId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ evidenceLinkId, body }: { evidenceLinkId: string; body: ReviewEvidenceRequest }) =>
      apiClient.post<EvidenceLink>(
        `/assessments/${assessmentId}/evidence/${evidenceLinkId}/review`,
        body,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.evidence(assessmentId) })
      // review outcomes feed directly into score/dashboard
      queryClient.invalidateQueries({ queryKey: keys.dashboard(assessmentId) })
      // ...and into whether the assessment may be finalized (ADR-0058):
      // an unreviewed proposal is a blocker, so accepting the last one
      // must re-enable Finalize without a page reload.
      queryClient.invalidateQueries({ queryKey: keys.finalizationReadiness(assessmentId) })
    },
  })
}

/**
 * Whether this assessment may be finalized, and what blocks it
 * (ADR-0058).
 *
 * The same rule is enforced server-side in transition_status — this
 * exists so the reviewer can see and fix the blockers rather than
 * discovering them as a 409 after pressing a button. It is a usability
 * affordance, not the integrity boundary.
 */
export function useFinalizationReadiness(assessmentId: string | undefined) {
  return useQuery({
    queryKey: keys.finalizationReadiness(assessmentId ?? ''),
    queryFn: () =>
      apiClient.get<FinalizationReadiness>(
        `/assessments/${assessmentId}/finalization-readiness`,
      ),
    enabled: !!assessmentId,
  })
}

/**
 * Check a finalized assessment against the seal written when it was
 * finalized (ADR-0060).
 *
 * Deliberately NOT run on render. Verification is a question somebody
 * asks — "is this record still the record?" — and an answer that
 * appears before anyone asked reads as decoration. It also costs a full
 * re-read and re-hash of the assessment, which is not something to do
 * every time a tab mounts.
 */
export function useVerifySeal(assessmentId: string | undefined) {
  return useQuery({
    queryKey: keys.sealVerification(assessmentId ?? ''),
    queryFn: () => apiClient.get<SealVerification>(`/assessments/${assessmentId}/verify`),
    enabled: false,
    // A verdict has a moment attached to it. Keeping a stale one around
    // would let the panel say "verified" about a check run before an
    // edit that has happened since.
    gcTime: 0,
  })
}

export function useDashboard(assessmentId: string | undefined) {
  return useQuery({
    queryKey: keys.dashboard(assessmentId ?? ''),
    queryFn: () => apiClient.get<DashboardReport>(`/assessments/${assessmentId}/dashboard`),
    enabled: !!assessmentId,
  })
}

export function useChat(assessmentId: string) {
  return useMutation({
    mutationFn: (question: string) =>
      apiClient.post<ChatResponse>(`/assessments/${assessmentId}/chat`, { question }),
  })
}

export function reportUrl(
  assessmentId: string,
  format: 'pdf' | 'xlsx',
  sanitized = false,
): string {
  const suffix = sanitized ? '?sanitized=true' : ''
  return `${API_BASE_URL}/assessments/${assessmentId}/report/${format}${suffix}`
}

// --- Practice findings (ADR-0030) ---

export function usePracticeFindings(assessmentId: string | undefined) {
  return useQuery({
    queryKey: keys.practiceFindings(assessmentId ?? ''),
    queryFn: () => apiClient.get<PracticeFinding[]>(`/assessments/${assessmentId}/practice-findings`),
    enabled: !!assessmentId,
  })
}

export function usePracticeFindingHistory(assessmentId: string, practiceReference: string | null) {
  return useQuery({
    queryKey: keys.practiceFindingHistory(assessmentId, practiceReference ?? ''),
    queryFn: () =>
      apiClient.get<PracticeFindingChange[]>(
        `/assessments/${assessmentId}/practice-findings/${practiceReference}/history`,
      ),
    enabled: !!practiceReference,
  })
}

export function useSetPracticeFinding(assessmentId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      practiceReference,
      status,
      rationale,
    }: {
      practiceReference: string
      status: PracticeFindingStatus
      rationale: string
    }) =>
      apiClient.put<PracticeFinding>(
        `/assessments/${assessmentId}/practice-findings/${practiceReference}`,
        { status, rationale },
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.practiceFindings(assessmentId) })
      // findings feed directly into score/dashboard (ADR-0030)
      queryClient.invalidateQueries({ queryKey: keys.dashboard(assessmentId) })
      // ...and a SATISFIED/NOT_APPLICABLE finding without supporting
      // evidence is itself a finalization blocker (ADR-0058).
      queryClient.invalidateQueries({ queryKey: keys.finalizationReadiness(assessmentId) })
    },
  })
}

// --- Evidence requests (ADR-0043) ---

export function useEvidenceRequests(assessmentId: string | undefined) {
  return useQuery({
    queryKey: keys.evidenceRequests(assessmentId ?? ''),
    queryFn: () =>
      apiClient.get<EvidenceRequest[]>(`/assessments/${assessmentId}/evidence-requests`),
    enabled: !!assessmentId,
  })
}

export function useRequestMoreEvidence(assessmentId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    // No requested_by: the server attributes this to the authenticated
    // identity and ignores anything the client claims (ADR-0061).
    mutationFn: ({ practiceReference, note }: { practiceReference: string; note: string }) =>
      apiClient.post<EvidenceRequest>(
        `/assessments/${assessmentId}/practice-findings/${practiceReference}/evidence-requests`,
        { note },
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.evidenceRequests(assessmentId) })
      queryClient.invalidateQueries({ queryKey: keys.finalizationReadiness(assessmentId) })
    },
  })
}

export function useResolveEvidenceRequest(assessmentId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ requestId }: { requestId: string }) =>
      apiClient.post<EvidenceRequest>(
        `/assessments/${assessmentId}/evidence-requests/${requestId}/resolve`,
        {},
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.evidenceRequests(assessmentId) })
      queryClient.invalidateQueries({ queryKey: keys.finalizationReadiness(assessmentId) })
    },
  })
}

// --- Sanitization (ADR-0032) ---

export function usePreviewSanitization(assessmentId: string) {
  return useMutation({
    mutationFn: (customTerms: string[]) =>
      apiClient.post<SanitizationPreview>(`/assessments/${assessmentId}/sanitization/preview`, {
        custom_terms: customTerms,
      }),
  })
}

export function useApproveSanitization(assessmentId: string) {
  return useMutation({
    mutationFn: ({ customTerms, approvedBy }: { customTerms: string[]; approvedBy: string }) =>
      apiClient.post<SanitizationApproval>(`/assessments/${assessmentId}/sanitization/approve`, {
        custom_terms: customTerms,
        approved_by: approvedBy,
      }),
  })
}
