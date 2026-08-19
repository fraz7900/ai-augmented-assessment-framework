import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { API_BASE_URL, apiClient } from './client'
import type {
  Assessment,
  AssessmentStatusChange,
  ChatResponse,
  CreateAssessmentRequest,
  DashboardReport,
  EvidenceLink,
  EvidenceQueueSummary,
  EvidenceRequest,
  EvidenceReviewStatus,
  DocumentSummary,
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
  // The organisation is part of the key, not just the URL (ADR-0063).
  // Without it, switching client would serve the previous one's
  // assessments out of the cache -- a stale list is a nuisance
  // everywhere else in this app and a confidentiality failure here.
  assessments: (organizationId: string | undefined) =>
    ['assessments', 'list', organizationId ?? ''] as const,
  assessment: (id: string) => ['assessments', id] as const,
  statusHistory: (id: string) => ['assessments', id, 'status-history'] as const,
  // The filter is part of the key. Without it, changing the filter
  // would serve the previous filter's rows out of the cache and the
  // control would look broken; with it, an invalidation after a
  // review still refreshes every filtered view of the same queue,
  // because they all share this prefix.
  evidence: (id: string, filters?: EvidenceFilters) =>
    ['assessments', id, 'evidence', filters ?? {}] as const,
  evidenceSummary: (id: string) => ['assessments', id, 'evidence', 'summary'] as const,
  // Every filtered list AND the summary sit under this prefix, so a
  // review decision invalidates all of them with one call. Passing
  // keys.evidence(id) here instead would only match the unfiltered
  // list, leaving a reviewer working inside a filter looking at a row
  // they had just decided on.
  evidenceAll: (id: string) => ['assessments', id, 'evidence'] as const,
  dashboard: (id: string) => ['assessments', id, 'dashboard'] as const,
  practiceFindings: (id: string) => ['assessments', id, 'practice-findings'] as const,
  practiceFindingHistory: (id: string, practiceReference: string) =>
    ['assessments', id, 'practice-findings', practiceReference, 'history'] as const,
  evidenceRequests: (id: string) => ['assessments', id, 'evidence-requests'] as const,
  finalizationReadiness: (id: string) =>
    ['assessments', id, 'finalization-readiness'] as const,
  sealVerification: (id: string) => ['assessments', id, 'seal-verification'] as const,
  assessmentDocuments: (id: string) => ['assessments', id, 'documents'] as const,
}

export function useAssessments(organizationId: string | undefined) {
  return useQuery({
    queryKey: keys.assessments(organizationId),
    queryFn: () =>
      apiClient.get<Assessment[]>(
        `/assessments?organization_id=${encodeURIComponent(organizationId ?? '')}`,
      ),
    // Nothing is fetched before the organisation is known: an unscoped
    // request would either 400 (two or more organisations) or quietly
    // answer for the only one, and the second is the habit worth not
    // forming.
    enabled: !!organizationId,
  })
}

export function useAssessment(id: string | undefined) {
  return useQuery({
    queryKey: keys.assessment(id ?? ''),
    queryFn: () => apiClient.get<Assessment>(`/assessments/${id}`),
    enabled: !!id,
  })
}

export function useCreateAssessment(organizationId: string | undefined) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: CreateAssessmentRequest) =>
      apiClient.post<Assessment>('/assessments', { ...body, organization_id: organizationId }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: keys.assessments(organizationId) }),
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
      // By prefix, without an organisation: a status change should
      // refresh whichever list is on screen, and this hook does not know
      // which organisation that is.
      queryClient.invalidateQueries({ queryKey: ['assessments', 'list'] })
    },
  })
}

export type EvidenceFilters = {
  review_status?: EvidenceReviewStatus
  domain?: string
  min_confidence?: number
  max_confidence?: number
}

function evidenceQueryString(filters: EvidenceFilters | undefined): string {
  if (!filters) return ''
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) {
    // An empty string is what a cleared <select> gives back, and it is
    // not a filter — sending it would ask the server for links whose
    // domain is "".
    if (value === undefined || value === '') continue
    params.set(key, String(value))
  }
  const query = params.toString()
  return query ? `?${query}` : ''
}

export function useEvidenceLinks(
  assessmentId: string | undefined,
  filters?: EvidenceFilters,
) {
  return useQuery({
    queryKey: keys.evidence(assessmentId ?? '', filters),
    queryFn: () =>
      apiClient.get<EvidenceLink[]>(
        `/assessments/${assessmentId}/evidence${evidenceQueryString(filters)}`,
      ),
    enabled: !!assessmentId,
  })
}

/**
 * Counts over the whole queue, never the filtered view (ADR-0065).
 *
 * Kept a separate request rather than folded into the list response so
 * that the totals a reviewer reads cannot move when they change a
 * filter — a "23 of 412" that becomes "23 of 23" answers nothing.
 */
export function useEvidenceSummary(assessmentId: string | undefined) {
  return useQuery({
    queryKey: keys.evidenceSummary(assessmentId ?? ''),
    queryFn: () =>
      apiClient.get<EvidenceQueueSummary>(`/assessments/${assessmentId}/evidence/summary`),
    enabled: !!assessmentId,
  })
}

export function useLinkEvidence(assessmentId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: LinkEvidenceRequest) =>
      apiClient.post<EvidenceLink>(`/assessments/${assessmentId}/evidence`, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.evidenceAll(assessmentId) }),
  })
}

export function useProposeMappings(assessmentId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => apiClient.post<EvidenceLink[]>(`/assessments/${assessmentId}/propose-mappings`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.evidenceAll(assessmentId) })
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
      queryClient.invalidateQueries({ queryKey: keys.evidenceAll(assessmentId) })
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

/**
 * The documents attached to this assessment (ADR-0062).
 *
 * What the evidence chooser offers. It used to call `useDocuments()`,
 * which lists every document on the instance — so a reviewer picking
 * evidence for one organisation's assessment was shown another
 * organisation's policies, and could link them.
 */
export function useAssessmentDocuments(assessmentId: string | undefined) {
  return useQuery({
    queryKey: keys.assessmentDocuments(assessmentId ?? ''),
    queryFn: () => apiClient.get<DocumentSummary[]>(`/assessments/${assessmentId}/documents`),
    enabled: !!assessmentId,
  })
}

export function useAttachDocument(assessmentId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (documentId: string) =>
      apiClient.post<DocumentSummary>(`/assessments/${assessmentId}/documents`, {
        document_id: documentId,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.assessmentDocuments(assessmentId) })
    },
  })
}

export function useDetachDocument(assessmentId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (documentId: string) =>
      apiClient.del<void>(`/assessments/${assessmentId}/documents/${documentId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.assessmentDocuments(assessmentId) })
    },
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
