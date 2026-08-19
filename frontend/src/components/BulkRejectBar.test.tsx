import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import BulkRejectBar from './BulkRejectBar'
import type { BulkReviewResult } from '../api/types'

// The control's job is to make an irreversible action deliberate
// (ADR-0067). So the tests are about the guard rails: that it confirms
// first, that it never offers to accept, and that it reports what it did
// not do.

const noop = () => {}

describe('BulkRejectBar', () => {
  it('shows nothing when there is no selection and no prior result', () => {
    const { container } = render(
      <BulkRejectBar
        selectedCount={0}
        isSubmitting={false}
        result={undefined}
        error={null}
        onReject={noop}
        onClear={noop}
      />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('never offers to accept in bulk', () => {
    // AGENTS.md rule 2. Rejecting withholds a compliance claim;
    // accepting fabricates one, and needs a human on each.
    render(
      <BulkRejectBar
        selectedCount={12}
        isSubmitting={false}
        result={undefined}
        error={null}
        onReject={noop}
        onClear={noop}
      />,
    )
    expect(screen.queryByRole('button', { name: /accept/i })).not.toBeInTheDocument()
  })

  it('does not reject on the first click', async () => {
    const onReject = vi.fn()
    render(
      <BulkRejectBar
        selectedCount={12}
        isSubmitting={false}
        result={undefined}
        error={null}
        onReject={onReject}
        onClear={noop}
      />,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Reject selected' }))
    expect(onReject).not.toHaveBeenCalled()
    expect(screen.getByText(/This cannot be undone/)).toBeInTheDocument()
  })

  it('says what rejecting actually does, and what it does not destroy', async () => {
    render(
      <BulkRejectBar
        selectedCount={3}
        isSubmitting={false}
        result={undefined}
        error={null}
        onReject={noop}
        onClear={noop}
      />,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Reject selected' }))
    expect(screen.getByText(/stays in the dashboard's gap list/)).toBeInTheDocument()
    expect(screen.getByText(/documents stay attached/)).toBeInTheDocument()
  })

  it('rejects only after confirmation, and passes the note along', async () => {
    const onReject = vi.fn()
    render(
      <BulkRejectBar
        selectedCount={2}
        isSubmitting={false}
        result={undefined}
        error={null}
        onReject={onReject}
        onClear={noop}
      />,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Reject selected' }))
    await userEvent.type(screen.getByLabelText(/Note/), 'Not about this practice')
    await userEvent.click(screen.getByRole('button', { name: 'Yes, reject 2' }))
    expect(onReject).toHaveBeenCalledWith('Not about this practice')
  })

  it('sends no note rather than an empty one', async () => {
    const onReject = vi.fn()
    render(
      <BulkRejectBar
        selectedCount={1}
        isSubmitting={false}
        result={undefined}
        error={null}
        onReject={onReject}
        onClear={noop}
      />,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Reject selected' }))
    await userEvent.click(screen.getByRole('button', { name: 'Yes, reject 1' }))
    expect(onReject).toHaveBeenCalledWith(undefined)
  })

  it('can be backed out of', async () => {
    const onReject = vi.fn()
    render(
      <BulkRejectBar
        selectedCount={5}
        isSubmitting={false}
        result={undefined}
        error={null}
        onReject={onReject}
        onClear={noop}
      />,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Reject selected' }))
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(onReject).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'Reject selected' })).toBeInTheDocument()
  })

  it('reports what it did not do as well as what it did', () => {
    // A reviewer who selected 40 and moved 38 needs to know, or the
    // count they act on next is wrong.
    const result: BulkReviewResult = {
      rejected_count: 38,
      skipped: [
        { evidence_link_id: 'a', review_status: 'accepted' },
        { evidence_link_id: 'b', review_status: 'rejected' },
      ],
    }
    render(
      <BulkRejectBar
        selectedCount={0}
        isSubmitting={false}
        result={result}
        error={null}
        onReject={noop}
        onClear={noop}
      />,
    )
    expect(screen.getByText(/Rejected 38 link\(s\)/)).toBeInTheDocument()
    expect(screen.getByText(/2 were already reviewed/)).toBeInTheDocument()
  })

  it('says nothing about skips when there were none', () => {
    render(
      <BulkRejectBar
        selectedCount={0}
        isSubmitting={false}
        result={{ rejected_count: 4, skipped: [] }}
        error={null}
        onReject={noop}
        onClear={noop}
      />,
    )
    expect(screen.getByText(/Rejected 4 link\(s\)/)).toBeInTheDocument()
    expect(screen.queryByText(/already reviewed/)).not.toBeInTheDocument()
  })

  it('surfaces a failure instead of implying the batch went through', () => {
    render(
      <BulkRejectBar
        selectedCount={3}
        isSubmitting={false}
        result={undefined}
        error={new Error('Assessment is finalized and cannot be modified.')}
        onReject={noop}
        onClear={noop}
      />,
    )
    expect(
      screen.getByText('Assessment is finalized and cannot be modified.'),
    ).toBeInTheDocument()
  })

  it('blocks a second submit while one is in flight', async () => {
    render(
      <BulkRejectBar
        selectedCount={3}
        isSubmitting
        result={undefined}
        error={null}
        onReject={noop}
        onClear={noop}
      />,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Reject selected' }))
    expect(screen.getByRole('button', { name: /Rejecting/ })).toBeDisabled()
  })
})
