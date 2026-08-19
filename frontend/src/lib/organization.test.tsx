import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { OrganizationProvider } from './organization'
import { useOrganizationScope } from './organizationContext'
import { apiClient } from '../api/client'
import type { Organization } from '../api/types'

// The organisation scope is what every scoped query reads (ADR-0063), so
// the cases that matter are the ones where it could quietly answer with
// the wrong client: a stored selection pointing at an organisation that
// no longer exists, and a reload that must not silently move the
// reviewer somewhere else.

function organization(overrides: Partial<Organization> = {}): Organization {
  return {
    id: 'org_default',
    name: 'Unassigned',
    created_at: '2026-08-19T12:00:00Z',
    ...overrides,
  }
}

function wrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>
      <OrganizationProvider>{children}</OrganizationProvider>
    </QueryClientProvider>
  )
  return Wrapper
}

beforeEach(() => {
  window.localStorage.clear()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('organization scope', () => {
  it('selects the only organization without anyone choosing', async () => {
    // The single-organisation deployment the charter scopes: the product
    // has to work without a decision being demanded first.
    vi.spyOn(apiClient, 'get').mockResolvedValue([organization()])

    const { result } = renderHook(() => useOrganizationScope(), { wrapper: wrapper() })

    await waitFor(() => expect(result.current.organizationId).toBe('org_default'))
  })

  it('restores the stored selection rather than the first organization', async () => {
    // A reviewer who reloads mid-assessment must not land on a different
    // client.
    window.localStorage.setItem('compliance-platform.organization-id', 'org-2')
    vi.spyOn(apiClient, 'get').mockResolvedValue([
      organization(),
      organization({ id: 'org-2', name: 'Coastal Utility' }),
    ])

    const { result } = renderHook(() => useOrganizationScope(), { wrapper: wrapper() })

    await waitFor(() => expect(result.current.organization?.name).toBe('Coastal Utility'))
  })

  it('falls back when the stored organization no longer exists', async () => {
    // Otherwise every scoped query would ask for a client this instance
    // does not have, and the app would show empty lists that look like
    // lost data.
    window.localStorage.setItem('compliance-platform.organization-id', 'org-deleted')
    vi.spyOn(apiClient, 'get').mockResolvedValue([organization()])

    const { result } = renderHook(() => useOrganizationScope(), { wrapper: wrapper() })

    await waitFor(() => expect(result.current.organizationId).toBe('org_default'))
  })

  it('reports no organization while the list is still loading', () => {
    // Scoped queries stay disabled until this is known, so an unscoped
    // request is never sent.
    vi.spyOn(apiClient, 'get').mockReturnValue(new Promise(() => {}))

    const { result } = renderHook(() => useOrganizationScope(), { wrapper: wrapper() })

    expect(result.current.organizationId).toBeUndefined()
    expect(result.current.isLoading).toBe(true)
  })
})
