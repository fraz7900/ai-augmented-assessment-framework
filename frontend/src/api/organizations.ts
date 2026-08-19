import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from './client'
import type { Organization } from './types'

// Which client an assessment and its documents belong to (ADR-0063).
//
// This is the one listing in the app that is deliberately unscoped: a
// chooser has to be able to name what it is choosing between. It returns
// names and ids, never any client's evidence.
export const organizationKeys = {
  list: ['organizations', 'list'] as const,
}

export function useOrganizations() {
  return useQuery({
    queryKey: organizationKeys.list,
    queryFn: () => apiClient.get<Organization[]>('/organizations'),
    // An instance always has at least one (the backend bootstraps it),
    // and organisations change about as often as clients are signed, so
    // there is nothing to gain from refetching this on every focus.
    staleTime: 5 * 60 * 1000,
  })
}

export function useCreateOrganization() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (name: string) => apiClient.post<Organization>('/organizations', { name }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: organizationKeys.list }),
  })
}

export function useRenameOrganization() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) =>
      apiClient.patch<Organization>(`/organizations/${id}`, { name }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: organizationKeys.list }),
  })
}
