import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import EvidenceRequestControls from './EvidenceRequestControls'
import { apiClient } from '../api/client'

// The form used to ask "your name" and send it. Since ADR-0061 the
// server attributes the request to the identity the proxy
// authenticated and ignores anything the client claims, so asking
// would invite someone to type a name that will not be used.

function renderOpen(identity: { actor: string; is_authenticated: boolean }) {
  vi.spyOn(apiClient, 'get').mockResolvedValue(identity)
  const onSubmit = vi.fn()
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
  render(<EvidenceRequestControls onSubmit={onSubmit} />, { wrapper })
  fireEvent.click(screen.getByRole('button', { name: /request more evidence/i }))
  return { onSubmit }
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('EvidenceRequestControls', () => {
  it('no longer asks who is making the request', () => {
    renderOpen({ actor: 'priya', is_authenticated: true })
    expect(screen.queryByLabelText(/requested by/i)).not.toBeInTheDocument()
    expect(screen.queryByPlaceholderText(/your name/i)).not.toBeInTheDocument()
  })

  it('shows the identity the request will be recorded under', async () => {
    // Removing the input without saying what replaced it would leave a
    // reviewer recording decisions under a name they cannot see.
    renderOpen({ actor: 'priya', is_authenticated: true })
    await waitFor(() => expect(screen.getByText(/recorded as/i)).toBeInTheDocument())
    expect(screen.getByText('priya')).toBeInTheDocument()
  })

  it('says so plainly when there is no identity to record', async () => {
    // A deployment not behind the authenticating proxy records every
    // request anonymously, and the person making it should know before
    // they make it — not discover it in the audit trail later.
    renderOpen({ actor: 'unauthenticated', is_authenticated: false })
    await waitFor(() =>
      expect(screen.getByText(/without an identity/i)).toBeInTheDocument(),
    )
  })

  it('submits the note alone, with nothing claiming to be a name', () => {
    const { onSubmit } = renderOpen({ actor: 'priya', is_authenticated: true })

    fireEvent.change(screen.getByLabelText(/evidence request note/i), {
      target: { value: 'Please send the access review export.' },
    })
    fireEvent.click(screen.getByRole('button', { name: /send request/i }))

    expect(onSubmit).toHaveBeenCalledWith('Please send the access review export.')
  })

  it('still requires a note, which is the one thing the server insists on', () => {
    renderOpen({ actor: 'priya', is_authenticated: true })
    // Previously an empty name also blocked submission; the note must
    // keep doing so on its own (MissingEvidenceRequestNoteError).
    expect(screen.getByRole('button', { name: /send request/i })).toBeDisabled()
  })
})
