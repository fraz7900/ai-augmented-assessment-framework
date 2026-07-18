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
