import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import EvidenceReviewControls from './EvidenceReviewControls'

// FR-13a: "re-reviewing an already-reviewed link must be prevented." This
// is the structural enforcement of that rule — verified here because a
// regression (controls staying clickable after review) would be a silent
// product-invariant violation, not just a cosmetic bug.
describe('EvidenceReviewControls', () => {
  it('offers accept/edit/reject when the link is pending', () => {
    render(
      <EvidenceReviewControls reviewStatus="pending" onAccept={vi.fn()} onReject={vi.fn()} onEdit={vi.fn()} />,
    )
    expect(screen.getByRole('button', { name: 'Accept' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Edit' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reject' })).toBeInTheDocument()
  })

  it.each(['accepted', 'edited', 'rejected'] as const)(
    'offers no review action once the link is %s',
    (reviewStatus) => {
      render(
        <EvidenceReviewControls reviewStatus={reviewStatus} onAccept={vi.fn()} onReject={vi.fn()} onEdit={vi.fn()} />,
      )
      expect(screen.queryByRole('button', { name: 'Accept' })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Edit' })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Reject' })).not.toBeInTheDocument()
    },
  )

  it('calls onAccept when Accept is clicked', async () => {
    const onAccept = vi.fn()
    render(<EvidenceReviewControls reviewStatus="pending" onAccept={onAccept} onReject={vi.fn()} onEdit={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: 'Accept' }))
    expect(onAccept).toHaveBeenCalledOnce()
  })

  it('calls onEdit with the corrected practice reference after Edit -> Save correction', async () => {
    const onEdit = vi.fn()
    render(<EvidenceReviewControls reviewStatus="pending" onAccept={vi.fn()} onReject={vi.fn()} onEdit={onEdit} />)
    await userEvent.click(screen.getByRole('button', { name: 'Edit' }))
    await userEvent.type(screen.getByLabelText('Corrected practice reference'), 'ACCESS-1b')
    await userEvent.click(screen.getByRole('button', { name: 'Save correction' }))
    expect(onEdit).toHaveBeenCalledWith('ACCESS-1b')
  })
})
