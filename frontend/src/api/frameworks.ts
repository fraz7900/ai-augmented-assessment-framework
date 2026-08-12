import { useQuery } from '@tanstack/react-query'
import { apiClient } from './client'
import type { FrameworkDefinition } from './types'

export function useFramework(name: string | undefined) {
  return useQuery({
    queryKey: ['framework', name],
    queryFn: () => apiClient.get<FrameworkDefinition>(`/frameworks/${encodeURIComponent(name!)}`),
    enabled: !!name,
    staleTime: Infinity, // framework definitions are static, versioned data (ADR-0002)
  })
}

// ADR-0053 built multi-version registry support (this endpoint, plus
// ?version= and CreateAssessmentRequest.framework_version) and disclosed
// that no screen reached any of it. This hook is the frontend half of
// that follow-up (ADR-0055).
//
// The endpoint returns [] for an unrecognised name rather than 404, so an
// empty list is a real answer ("nothing known about this framework"), not
// an error to surface.
export function useFrameworkVersions(name: string | undefined) {
  return useQuery({
    queryKey: ['framework-versions', name],
    queryFn: () =>
      apiClient.get<string[]>(`/frameworks/${encodeURIComponent(name!)}/versions`),
    enabled: !!name,
    staleTime: Infinity, // static, versioned data — same rationale as useFramework
  })
}
