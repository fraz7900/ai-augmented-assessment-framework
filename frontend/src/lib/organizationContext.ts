import { createContext, useContext } from 'react'
import type { Organization } from '../api/types'

// The context and its hook live apart from the provider component so
// that organization.tsx exports a component and nothing else -- the
// repo's lint carries exactly two fast-refresh warnings, both
// pre-existing in EvidenceSourceBadge.tsx, and a third from a new file
// would be a small mess left for someone else to wonder about.

// The generated schema types `id` as optional, because SQLModel gives it
// a default_factory and FastAPI therefore does not mark it required. On a
// response it is always present, so the list is narrowed once in the
// provider rather than asserted with `!` at each of the dozen places
// that need a string.
export type IdentifiedOrganization = Organization & { id: string }

export type OrganizationContextValue = {
  organizations: IdentifiedOrganization[]
  organization: IdentifiedOrganization | undefined
  organizationId: string | undefined
  setOrganizationId: (id: string) => void
  isLoading: boolean
}

export const OrganizationContext = createContext<OrganizationContextValue | null>(null)

export function useOrganizationScope(): OrganizationContextValue {
  const value = useContext(OrganizationContext)
  if (value === null) {
    throw new Error('useOrganizationScope must be used inside an OrganizationProvider')
  }
  return value
}
