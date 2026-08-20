import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import ReviewProgressBar from './ReviewProgressBar'
import type { Situation } from '../api/types'

// The bar exists so "how much of this is still unreviewed" reads at a
// glance instead of being one integer among five (ADR-0068). The tests
// worth having are about what it must not imply: that rejecting is a
// failure, that a bar which does not add up is fine, or that provisional
// scores are final.

function situation(overrides: Partial<Situation> = {}): Situation {
  return {
    assessment_id: 'a1',
    assessment_name: 'Test',
    organization_name: 'Client A',
    framework_name: 'C2M2',
    scoring_model: 'cumulative_mil',
    status: 'draft',
    total_evidence_links: 100,
    accepted_count: 20,
    edited_count: 5,
    rejected_count: 60,
    pending_ai_review_count: 15,
    unpopulated_domains: [],
    unsupported_satisfied_practices: [],
    unsupported_not_applicable_practices: [],
    finalization_seal: null,
    so_what: [],
    ...overrides,
  }
}

describe('ReviewProgressBar', () => {
  it('shows every review state with its count', () => {
    render(<ReviewProgressBar situation={situation()} />)
    for (const [count, label] of [
      ['20', 'Accepted'],
      ['5', 'Edited'],
      ['60', 'Rejected'],
      ['15', 'Awaiting review'],
    ] as const) {
      expect(screen.getByText(label)).toBeInTheDocument()
      expect(screen.getByText(count)).toBeInTheDocument()
    }
  })

  it('leads with what is still unreviewed, in the terms that matter', () => {
    render(<ReviewProgressBar situation={situation()} />)
    expect(
      screen.getByText(/15% of linked evidence is still awaiting a human decision/),
    ).toBeInTheDocument()
    expect(screen.getByText(/cannot be finalized yet/)).toBeInTheDocument()
  })

  it('says nothing about provisional scores once everything is reviewed', () => {
    render(
      <ReviewProgressBar
        situation={situation({ accepted_count: 40, pending_ai_review_count: 0 })}
      />,
    )
    expect(screen.queryByText(/awaiting a human decision/)).not.toBeInTheDocument()
  })

  it('does not treat rejection as a failure state', () => {
    // Retrieval precision was measured at 0.012, so rejecting is the
    // expected outcome for most of the queue. Painting it red would
    // report healthy review work as something going wrong.
    render(<ReviewProgressBar situation={situation()} />)
    expect(screen.getByText(/declined; the practice stays a gap/)).toBeInTheDocument()
    const rejectedSwatch = screen.getByText('Rejected').closest('li')
    expect(rejectedSwatch?.querySelector('.bg-red-500')).toBeNull()
    expect(rejectedSwatch?.querySelector('.bg-slate-400')).not.toBeNull()
  })

  it('explains what each state means for the score', () => {
    render(<ReviewProgressBar situation={situation()} />)
    expect(screen.getByText(/counts toward the score/)).toBeInTheDocument()
    expect(screen.getByText(/blocks finalization until decided/)).toBeInTheDocument()
  })

  it('describes the whole breakdown for a reader who cannot see it', () => {
    render(<ReviewProgressBar situation={situation()} />)
    expect(
      screen.getByLabelText(
        'Accepted: 20 of 100, Edited: 5 of 100, Rejected: 60 of 100, Awaiting review: 15 of 100',
      ),
    ).toBeInTheDocument()
  })

  it('omits an empty state from the bar description', () => {
    render(<ReviewProgressBar situation={situation({ edited_count: 0, accepted_count: 25 })} />)
    expect(screen.getByLabelText(/^Accepted: 25 of 100, Rejected/)).toBeInTheDocument()
  })

  it('shows a remainder rather than a bar that quietly stops short', () => {
    // If a fifth review status is ever added without a segment here, an
    // obviously odd bar is a far better failure than a confidently
    // wrong one.
    render(
      <ReviewProgressBar
        situation={situation({ accepted_count: 20, edited_count: 5, rejected_count: 50, pending_ai_review_count: 15 })}
      />,
    )
    expect(screen.getByText('Other')).toBeInTheDocument()
    expect(screen.getByText(/a review state this dashboard does not know/)).toBeInTheDocument()
    expect(screen.getByText('10')).toBeInTheDocument()
  })

  it('says there is nothing to show rather than drawing an empty bar', () => {
    render(
      <ReviewProgressBar
        situation={situation({
          total_evidence_links: 0,
          accepted_count: 0,
          edited_count: 0,
          rejected_count: 0,
          pending_ai_review_count: 0,
        })}
      />,
    )
    expect(screen.getByText(/no review progress to show/)).toBeInTheDocument()
  })
})
