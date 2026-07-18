import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { API_BASE_URL, apiClient } from './client'
import type {
  Assessment,
  AssessmentStatusChange,
  ChatResponse,
  CreateAssessmentRequest,
  DashboardReport,
  EvidenceLink,
  LinkEvidenceRequest,
  ReviewEvidenceRequest,
  StatusTransitionRequest,
} from './types'

const keys = {
  assessments: ['assessments'] as const,
  assessment: (id: string) => ['assessments', id] as const,
  statusHistory: (id: string) => ['assessments', id, 'status-history'] as const,
  evidence: (id: string) => ['assessments', id, 'evidence'] as const,
  dashboard: (id: string) => ['assessments', id, 'dashboard'] as const,
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
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.evidence(assessmentId) }),
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

export function reportUrl(assessmentId: string, format: 'pdf' | 'xlsx'): string {
  return `${API_BASE_URL}/assessments/${assessmentId}/report/${format}`
}
