import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { useOrganizations } from '../api/organizations'
import { OrganizationContext } from './organizationContext'
import type { IdentifiedOrganization } from './organizationContext'

// Which client the reviewer is currently working on (ADR-0063).
//
// Held in one place, at the app shell, because every scoped query needs
// the same answer and a page that read it from its own state could show
// one organisation's assessments beside another's documents -- which is
// the confusion the whole boundary exists to prevent.
//
// Persisted, because a reviewer who reloads mid-assessment should not
// silently land on a different client. Validated against the server's
// list on every load for the same reason: a stored id whose organisation
// has been renamed is fine, but one that no longer exists must not leave
// the app querying a client that is not there.
const STORAGE_KEY = 'compliance-platform.organization-id'

function readStoredId(): string | null {
  try {
    return window.localStorage.getItem(STORAGE_KEY)
  } catch {
    // Private-browsing modes can throw on localStorage access. Losing the
    // selection is a far better outcome than a blank page.
    return null
  }
}

export function OrganizationProvider({ children }: { children: ReactNode }) {
  const { data, isLoading } = useOrganizations()
  const [selectedId, setSelectedId] = useState<string | null>(() => readStoredId())

  const organizations = useMemo(
    () =>
      (data ?? []).filter(
        (organization): organization is IdentifiedOrganization =>
          typeof organization.id === 'string',
      ),
    [data],
  )

  const resolved = useMemo(() => {
    if (organizations.length === 0) return undefined
    const stored = organizations.find((organization) => organization.id === selectedId)
    // Falling back to the first is safe precisely because it is only
    // reachable when the stored id names nothing on this instance.
    return stored ?? organizations[0]
  }, [organizations, selectedId])

  useEffect(() => {
    if (!resolved || resolved.id === selectedId) return
    setSelectedId(resolved.id)
  }, [resolved, selectedId])

  const setOrganizationId = useCallback((id: string) => {
    setSelectedId(id)
    try {
      window.localStorage.setItem(STORAGE_KEY, id)
    } catch {
      // See readStoredId: the selection still works for this session.
    }
  }, [])

  const value = useMemo(
    () => ({
      organizations,
      organization: resolved,
      organizationId: resolved?.id,
      setOrganizationId,
      isLoading,
    }),
    [organizations, resolved, setOrganizationId, isLoading],
  )

  return <OrganizationContext.Provider value={value}>{children}</OrganizationContext.Provider>
}
