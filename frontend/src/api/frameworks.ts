import { useQuery } from '@tanstack/react-query'
import { apiClient } from './client'
import type { FrameworkDefinition } from './types'

/**
 * The framework definition an assessment is actually pinned to.
 *
 * `version` is part of the cache key, not just the URL. Without it,
 * react-query would serve a NIST CSF 2.0 definition to a 1.1-pinned
 * assessment purely because 2.0 was fetched first — the two versions
 * share a framework name and, since ADR-0055, share no practice ids at
 * all ("ID.AM-1" vs "ID.AM-01"). The Evidence tab uses this definition
 * to validate practice references and to render practice text, so a
 * cache collision would show a reviewer the wrong control wording for
 * the version they are assessing against.
 *
 * `version === undefined` means "whatever the registry considers
 * latest", which is exactly what a legacy assessment with a null
 * `framework_version` needs: no `?version=` is sent, and the backend
 * resolves latest as it always did (ADR-0053).
 */
export function useFramework(name: string | undefined, version?: string | null) {
  return useQuery({
    queryKey: ['framework', name, version ?? null],
    queryFn: () => {
      const query = version ? `?version=${encodeURIComponent(version)}` : ''
      return apiClient.get<FrameworkDefinition>(
        `/frameworks/${encodeURIComponent(name!)}${query}`,
      )
    },
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
