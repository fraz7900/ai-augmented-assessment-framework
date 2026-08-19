import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import EvidenceQueueFilters from './EvidenceQueueFilters'
import type { EvidenceQueueSummary } from '../api/types'

// The control narrows what a reviewer reads (ADR-0065). The tests that
// matter are not "does the dropdown change state" — they are the ones
// covering what stops a filter from misleading: totals that come from the
// whole queue, and a visible count of the links no domain filter can
// reach.

const summary: EvidenceQueueSummary = {
  total: 412,
  by_status: { pending: 380, accepted: 26, edited: 4, rejected: 2 },
  by_domain: [
    { short_code: 'ACCESS', full_name: 'Identity and Access Management', total: 184, pending: 180 },
    { short_code: 'ASSET', full_name: 'Asset, Change, and Configuration Management', total: 96, pending: 90 },
  ],
  unmapped: 3,
}

describe('EvidenceQueueFilters', () => {
  it('says what the filtered view is a subset of', () => {
    render(
      <EvidenceQueueFilters filters={{ domain: 'ACCESS' }} summary={summary} shownCount={184} onChange={vi.fn()} />,
    )
    expect(screen.getByText(/of 412/)).toBeInTheDocument()
    expect(screen.getByText('184')).toBeInTheDocument()
  })

  it('discloses the links no domain filter can reach', () => {
    render(<EvidenceQueueFilters filters={{}} summary={summary} shownCount={412} onChange={vi.fn()} />)
    expect(
      screen.getByText(/3 link\(s\) cite a practice outside this framework version/),
    ).toBeInTheDocument()
  })

  it('says nothing about unmapped links when there are none', () => {
    render(
      <EvidenceQueueFilters
        filters={{}}
        summary={{ ...summary, unmapped: 0 }}
        shownCount={412}
        onChange={vi.fn()}
      />,
    )
    expect(screen.queryByText(/cite a practice outside/)).not.toBeInTheDocument()
  })

  it('offers only domains that have links in them', () => {
    render(<EvidenceQueueFilters filters={{}} summary={summary} shownCount={412} onChange={vi.fn()} />)
    const domain = screen.getByLabelText('Domain')
    expect(domain).toHaveTextContent('ACCESS')
    expect(domain).toHaveTextContent('ASSET')
    // C2M2 has ten domains; the eight with nothing queued are not offered.
    expect(domain).not.toHaveTextContent('THREAT')
  })

  it('shows how much of each domain is still awaiting review', () => {
    render(<EvidenceQueueFilters filters={{}} summary={summary} shownCount={412} onChange={vi.fn()} />)
    expect(screen.getByRole('option', { name: /ACCESS.*180 of 184 awaiting/ })).toBeInTheDocument()
  })

  it('reports a domain choice to the caller', async () => {
    const onChange = vi.fn()
    render(<EvidenceQueueFilters filters={{}} summary={summary} shownCount={412} onChange={onChange} />)
    await userEvent.selectOptions(screen.getByLabelText('Domain'), 'ASSET')
    expect(onChange).toHaveBeenCalledWith({ domain: 'ASSET' })
  })

  it('clears a filter back to undefined rather than an empty string', async () => {
    // An empty string would be sent to the API as `domain=`, which asks
    // for links whose domain is the empty string — none.
    const onChange = vi.fn()
    render(
      <EvidenceQueueFilters filters={{ domain: 'ASSET' }} summary={summary} shownCount={96} onChange={onChange} />,
    )
    await userEvent.selectOptions(screen.getByLabelText('Domain'), '')
    expect(onChange).toHaveBeenCalledWith({ domain: undefined })
  })

  it('translates a confidence band into the bounds the API takes', async () => {
    const onChange = vi.fn()
    render(<EvidenceQueueFilters filters={{}} summary={summary} shownCount={412} onChange={onChange} />)
    await userEvent.selectOptions(screen.getByLabelText('Retrieval confidence'), 'measured')
    expect(onChange).toHaveBeenCalledWith({ min_confidence: 0.65, max_confidence: 0.78 })
  })

  it('warns that a high-confidence band is uncalibrated, not trustworthy', () => {
    // R-16: correct pairs were measured at 0.65–0.78. Above that nobody
    // has checked, so the UI must not let a big number read as safety.
    render(
      <EvidenceQueueFilters
        filters={{ min_confidence: 0.78 }}
        summary={summary}
        shownCount={7}
        onChange={vi.fn()}
      />,
    )
    expect(screen.getByText(/No correct match has been measured above 0.78/)).toBeInTheDocument()
  })

  it('offers no way to act on the filtered set', () => {
    // The requested "accept all above 0.85" is what this control must not
    // grow into (AGENTS.md rule 2). Clear filters is the only button here.
    render(
      <EvidenceQueueFilters
        filters={{ min_confidence: 0.78 }}
        summary={summary}
        shownCount={7}
        onChange={vi.fn()}
      />,
    )
    const buttons = screen.getAllByRole('button')
    expect(buttons).toHaveLength(1)
    expect(buttons[0]).toHaveTextContent('Clear filters')
  })

  it('offers no clear action when nothing is filtered', () => {
    render(<EvidenceQueueFilters filters={{}} summary={summary} shownCount={412} onChange={vi.fn()} />)
    expect(screen.queryByRole('button', { name: 'Clear filters' })).not.toBeInTheDocument()
  })

  it('still renders before the summary has loaded', () => {
    render(<EvidenceQueueFilters filters={{}} summary={undefined} shownCount={0} onChange={vi.fn()} />)
    expect(screen.getByLabelText('Domain')).toBeInTheDocument()
    expect(screen.queryByText(/of 412/)).not.toBeInTheDocument()
  })
})
