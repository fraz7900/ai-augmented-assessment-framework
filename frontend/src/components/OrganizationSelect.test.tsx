import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import OrganizationSelect from './OrganizationSelect'
import { OrganizationProvider } from '../lib/organization'
import { apiClient } from '../api/client'
import type { Organization } from '../api/types'

function organization(overrides: Partial<Organization> = {}): Organization {
  return {
    id: 'org_default',
    name: 'Unassigned',
    created_at: '2026-08-19T12:00:00Z',
    ...overrides,
  }
}

function renderSelect(organizations: Organization[]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>
      <OrganizationProvider>{children}</OrganizationProvider>
    </QueryClientProvider>
  )
  vi.spyOn(apiClient, 'get').mockResolvedValue(organizations)
  render(<OrganizationSelect />, { wrapper: Wrapper })
}

beforeEach(() => {
  window.localStorage.clear()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('OrganizationSelect', () => {
  it('shows the selector even when there is only one organization', async () => {
    // Hiding it on a single-organisation instance would mean the control
    // appears for the first time on the day a second client is added --
    // the day a reviewer is most likely to be looking at the wrong one.
    renderSelect([organization()])

    expect(await screen.findByRole('combobox', { name: /organization/i })).toBeInTheDocument()
  })

  it('lists every organization to switch between', async () => {
    renderSelect([organization(), organization({ id: 'org-2', name: 'Coastal Utility' })])

    expect(await screen.findByRole('option', { name: 'Unassigned' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Coastal Utility' })).toBeInTheDocument()
  })

  it('switches the scope when a different organization is chosen', async () => {
    renderSelect([organization(), organization({ id: 'org-2', name: 'Coastal Utility' })])
    const select = await screen.findByRole('combobox', { name: /organization/i })

    fireEvent.change(select, { target: { value: 'org-2' } })

    await waitFor(() => expect((select as HTMLSelectElement).value).toBe('org-2'))
  })

  it('switches to a newly created organization rather than staying put', async () => {
    // Creating a client and then still looking at the previous one is
    // never what was meant.
    renderSelect([organization()])
    vi.spyOn(apiClient, 'post').mockResolvedValue(
      organization({ id: 'org-2', name: 'Coastal Utility' }),
    )
    fireEvent.click(await screen.findByRole('button', { name: /new/i }))
    fireEvent.change(screen.getByLabelText(/new organization name/i), {
      target: { value: 'Coastal Utility' },
    })

    fireEvent.click(screen.getByRole('button', { name: /^add$/i }))

    await waitFor(() =>
      expect(apiClient.post).toHaveBeenCalledWith('/organizations', { name: 'Coastal Utility' }),
    )
  })

  it('shows the server refusal when a name is already taken', async () => {
    renderSelect([organization()])
    vi.spyOn(apiClient, 'post').mockRejectedValue(
      new Error("An organization named 'Unassigned' already exists."),
    )
    fireEvent.click(await screen.findByRole('button', { name: /new/i }))
    fireEvent.change(screen.getByLabelText(/new organization name/i), {
      target: { value: 'Unassigned' },
    })

    fireEvent.click(screen.getByRole('button', { name: /^add$/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/already exists/i)
  })
})
