import { describe, expect, it } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import DomainCompletionChart from './DomainCompletionChart'
import type { DomainProgress, OverallSummary } from '../api/types'

// The chart's job is to be read correctly, so the tests are about what it
// refuses to imply (ADR-0066): that a bar is a maturity score, that a
// nearly-full bar means nearly-scoring, or that a domain with nothing
// transcribed is a domain with nothing done.

const milOverall: OverallSummary = {
  scoring_model: 'cumulative_mil',
  headline: '2 of 10 domains at MIL1 or above.',
  populated_domains: 2,
  total_domains: 10,
  domains_at_mil1_or_above: 2,
}

const coverageOverall: OverallSummary = {
  scoring_model: 'coverage',
  headline: '48% overall coverage.',
  populated_domains: 6,
  total_domains: 6,
  overall_coverage_fraction: 0.48,
}

function progress(overrides: Partial<DomainProgress> = {}): DomainProgress {
  return {
    short_code: 'ACCESS',
    full_name: 'Identity and Access Management',
    met_practices: 5,
    total_practices: 10,
    score: 1,
    blocking_mil: null,
    blocking_practice_count: null,
    ...overrides,
  }
}

describe('DomainCompletionChart', () => {
  it('shows completion as a count, not only as a bar', () => {
    render(<DomainCompletionChart progress={[progress()]} overall={milOverall} />)
    expect(screen.getByText(/5 of 10 practices/)).toBeInTheDocument()
  })

  it('shows the domain score next to the bar, in the units of its scoring model', () => {
    render(<DomainCompletionChart progress={[progress({ score: 2 })]} overall={milOverall} />)
    expect(screen.getByText('MIL2')).toBeInTheDocument()
  })

  it('labels a coverage framework in coverage terms', () => {
    render(
      <DomainCompletionChart progress={[progress({ score: 0.5 })]} overall={coverageOverall} />,
    )
    expect(screen.getByText('50% coverage')).toBeInTheDocument()
    expect(screen.queryByText(/MIL/)).not.toBeInTheDocument()
  })

  it('explains why a nearly-complete domain still scores zero', () => {
    // The misreading this component exists to prevent: 9 of 10 met is a
    // 90% bar next to MIL0, which looks like a defect unless the gate is
    // named.
    render(
      <DomainCompletionChart
        progress={[
          progress({ met_practices: 9, total_practices: 10, score: 0, blocking_mil: 1, blocking_practice_count: 1 }),
        ]}
        overall={milOverall}
      />,
    )
    expect(
      screen.getByText(/1 practice\(s\) at MIL1 still unmet, so this domain cannot score above MIL0/),
    ).toBeInTheDocument()
  })

  it('names the next gate once a level has been cleared', () => {
    render(
      <DomainCompletionChart
        progress={[progress({ score: 1, blocking_mil: 2, blocking_practice_count: 4 })]}
        overall={milOverall}
      />,
    )
    expect(screen.getByText(/4 practice\(s\) at MIL2 still unmet/)).toBeInTheDocument()
    expect(screen.getByText(/cannot score above MIL1/)).toBeInTheDocument()
  })

  it('says nothing about a gate when nothing is blocked', () => {
    render(
      <DomainCompletionChart
        progress={[progress({ met_practices: 10, total_practices: 10, score: 3 })]}
        overall={milOverall}
      />,
    )
    expect(screen.queryByText(/still unmet/)).not.toBeInTheDocument()
  })

  it('warns that bars are not the maturity score on a MIL framework', () => {
    render(<DomainCompletionChart progress={[progress()]} overall={milOverall} />)
    expect(screen.getByText(/They are not the maturity score/)).toBeInTheDocument()
  })

  it('does not carry that warning on a coverage framework, where they are the same measure', () => {
    render(<DomainCompletionChart progress={[progress()]} overall={coverageOverall} />)
    expect(screen.queryByText(/They are not the maturity score/)).not.toBeInTheDocument()
    expect(screen.getByText(/same measure as this framework's coverage score/)).toBeInTheDocument()
  })

  it('orders the worst domain first, because that is the next place to work', () => {
    render(
      <DomainCompletionChart
        progress={[
          progress({ short_code: 'NEARLY', full_name: 'Nearly Done', met_practices: 9, total_practices: 10 }),
          progress({ short_code: 'WORST', full_name: 'Barely Started', met_practices: 1, total_practices: 20 }),
          progress({ short_code: 'MIDDLE', full_name: 'Half Way', met_practices: 5, total_practices: 10 }),
        ]}
        overall={milOverall}
      />,
    )
    const codes = screen.getAllByRole('listitem').map((item) => within(item).getByText(/^[A-Z]+$/).textContent)
    expect(codes).toEqual(['WORST', 'MIDDLE', 'NEARLY'])
  })

  it('describes each bar for a reader who cannot see it', () => {
    render(
      <DomainCompletionChart
        progress={[progress({ met_practices: 3, total_practices: 12, score: 0 })]}
        overall={milOverall}
      />,
    )
    expect(
      screen.getByLabelText(
        'Identity and Access Management: 3 of 12 applicable practices met, scoring MIL0',
      ),
    ).toBeInTheDocument()
  })

  it('says there is nothing to chart rather than drawing an empty frame', () => {
    // A framework whose domains are not transcribed yet (ADR-0009) has
    // no completion to show. Empty bars would report an absence as a gap.
    render(<DomainCompletionChart progress={[]} overall={milOverall} />)
    expect(screen.getByText(/nothing to chart/)).toBeInTheDocument()
  })
})
