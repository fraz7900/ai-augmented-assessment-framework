import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import ScoreHeadline from './ScoreHeadline'
import type { OverallSummary } from '../api/types'

// R-15: a cumulative_mil score (whole-number MIL 0-3) and a coverage score
// (0.0-1.0 fraction) mean different things and must never be blended into
// one fabricated number. Verifies the component renders the correct
// scoring-model-specific stat and never both / neither.
describe('ScoreHeadline', () => {
  it('shows the MIL1+ domain count for a cumulative_mil framework, not a coverage percentage', () => {
    const overall: OverallSummary = {
      scoring_model: 'cumulative_mil',
      headline: '1 of 2 populated domains at MIL1 or above.',
      populated_domains: 2,
      total_domains: 10,
      domains_at_mil1_or_above: 1,
      overall_coverage_fraction: null,
    }
    render(<ScoreHeadline overall={overall} />)
    expect(screen.getByText(overall.headline)).toBeInTheDocument()
    expect(screen.getByText(/1 domain\(s\) at MIL1 or above/)).toBeInTheDocument()
    expect(screen.queryByText(/% overall coverage/)).not.toBeInTheDocument()
  })

  it('shows the coverage percentage for a coverage framework, not a MIL count', () => {
    const overall: OverallSummary = {
      scoring_model: 'coverage',
      headline: 'NIST CSF 2.0 coverage assessment complete.',
      populated_domains: 6,
      total_domains: 6,
      domains_at_mil1_or_above: null,
      overall_coverage_fraction: 0.62,
    }
    render(<ScoreHeadline overall={overall} />)
    expect(screen.getByText(overall.headline)).toBeInTheDocument()
    expect(screen.getByText(/62% overall coverage/)).toBeInTheDocument()
    expect(screen.queryByText(/at MIL1 or above/)).not.toBeInTheDocument()
  })
})
