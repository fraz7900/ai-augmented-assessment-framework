import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import FinalizationSeal from './FinalizationSeal'
import type { SealVerification } from '../api/types'

const SEAL = 'a'.repeat(64)

function verification(overrides: Partial<SealVerification> = {}): SealVerification {
  return {
    assessment_id: 'a-1',
    status: 'verified',
    sealed_digest: SEAL,
    computed_digest: SEAL,
    sealed_at: '2026-08-18T12:00:00Z',
    seal_version: '2',
    detail: 'The stored record still matches the seal written when this assessment was finalized.',
    ...overrides,
  }
}

function renderPanel(props: Partial<Parameters<typeof FinalizationSeal>[0]> = {}) {
  const onVerify = vi.fn()
  render(
    <FinalizationSeal
      seal={SEAL}
      verification={undefined}
      isVerifying={false}
      error={null}
      onVerify={onVerify}
      {...props}
    />,
  )
  return { onVerify }
}

// The four verification states are the whole point of this panel: a
// boolean would collapse "no seal exists" and "the seal does not match"
// into the same answer, and they are opposite situations.
describe('FinalizationSeal', () => {
  it('shows the digest, because its value is being comparable to an exported copy', () => {
    renderPanel()
    expect(screen.getByText(SEAL)).toBeInTheDocument()
    expect(screen.getByText(/printed on every exported report/i)).toBeInTheDocument()
  })

  it('does not claim anything until someone asks', () => {
    // A verdict that appears before it was requested reads as
    // decoration, and this one costs a full re-read and re-hash.
    renderPanel()
    expect(screen.queryByText(/unaltered/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/has changed/i)).not.toBeInTheDocument()
  })

  it('runs the check when asked', () => {
    const { onVerify } = renderPanel()
    fireEvent.click(screen.getByRole('button', { name: /check this record/i }))
    expect(onVerify).toHaveBeenCalledOnce()
  })

  it('reports an intact record plainly', () => {
    renderPanel({ verification: verification() })
    expect(screen.getByText(/unaltered since finalization/i)).toBeInTheDocument()
  })

  it('shows both digests when they disagree, not just a verdict', () => {
    // Side by side they turn "the app says something is wrong" into
    // something a person can carry to whoever else holds a copy.
    renderPanel({
      verification: verification({
        status: 'altered',
        computed_digest: 'b'.repeat(64),
        detail: 'The stored record no longer matches the seal.',
      }),
    })
    expect(screen.getByText(/this record has changed since it was finalized/i)).toBeInTheDocument()
    expect(screen.getByText('a'.repeat(64))).toBeInTheDocument()
    expect(screen.getByText('b'.repeat(64))).toBeInTheDocument()
  })

  it('treats an unsealed assessment as unverified, not as a failure', () => {
    // Finalized before sealing existed. Rendering this in red would say
    // untrustworthy, which is a different claim entirely.
    renderPanel({
      seal: null,
      verification: verification({
        status: 'unsealed',
        sealed_digest: null,
        computed_digest: null,
        detail: 'This assessment carries no finalization seal.',
      }),
    })
    expect(screen.getByText(/no seal to check against/i)).toBeInTheDocument()
    expect(screen.getByText(/deliberately not sealed now/i)).toBeInTheDocument()
  })

  it('separates "this build cannot check it" from "it does not match"', () => {
    renderPanel({
      verification: verification({
        status: 'unverifiable',
        detail: "Seal version '9' is not known to this build.",
      }),
    })
    expect(screen.getByText(/cannot check that seal/i)).toBeInTheDocument()
    expect(screen.queryByText(/has changed since it was finalized/i)).not.toBeInTheDocument()
  })

  it('surfaces a failed request instead of looking like a verdict', () => {
    renderPanel({ error: new Error('Failed to fetch') })
    expect(screen.getByText('Failed to fetch')).toBeInTheDocument()
  })

  it('disables the button while the check is running', () => {
    renderPanel({ isVerifying: true })
    expect(screen.getByRole('button', { name: /checking/i })).toBeDisabled()
  })
})
