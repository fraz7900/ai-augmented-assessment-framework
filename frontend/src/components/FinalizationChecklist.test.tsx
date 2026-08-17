import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import FinalizationChecklist from './FinalizationChecklist'
import type { FinalizationBlocker, FinalizationReadiness } from '../api/types'

// ADR-0058. The reviewer must be able to see WHY finalization is blocked
// before pressing the button, and a finalized assessment must never be
// described as provisional.

function blocker(overrides: Partial<FinalizationBlocker> = {}): FinalizationBlocker {
  return {
    category: 'pending_ai_review',
    count: 3,
    affected_ids: ['link-1', 'link-2', 'link-3'],
    summary: '3 AI-proposed evidence link(s) still await human review.',
    ...overrides,
  }
}

function readiness(overrides: Partial<FinalizationReadiness> = {}): FinalizationReadiness {
  return {
    assessment_id: 'a1',
    status: 'in_review',
    is_ready: false,
    blockers: [blocker()],
    ...overrides,
  }
}

describe('FinalizationChecklist', () => {
  it('says it is checking rather than rendering a misleading empty state', () => {
    render(<FinalizationChecklist readiness={undefined} isLoading isFinalized={false} />)
    expect(screen.getByText(/checking finalization readiness/i)).toBeInTheDocument()
  })

  it('confirms readiness when nothing is outstanding', () => {
    render(
      <FinalizationChecklist
        readiness={readiness({ is_ready: true, blockers: [] })}
        isLoading={false}
        isFinalized={false}
      />,
    )
    expect(screen.getByText(/ready to finalize/i)).toBeInTheDocument()
    // States plainly that gaps are not a blocker, so a reviewer with a
    // non-compliant result does not think they must fix it first.
    expect(screen.getByText(/gaps do not block finalization/i)).toBeInTheDocument()
    expect(screen.queryByTestId('finalization-blockers')).not.toBeInTheDocument()
  })

  it('lists each blocker with its actionable summary', () => {
    render(
      <FinalizationChecklist readiness={readiness()} isLoading={false} isFinalized={false} />,
    )
    expect(screen.getByTestId('finalization-blockers')).toBeInTheDocument()
    expect(screen.getByText(/1 item\(s\) to resolve/i)).toBeInTheDocument()
    expect(screen.getByText(/still await human review/i)).toBeInTheDocument()
    expect(screen.getByText(/link-1, link-2, link-3/)).toBeInTheDocument()
  })

  it('shows every blocker category at once', () => {
    render(
      <FinalizationChecklist
        readiness={readiness({
          blockers: [
            blocker(),
            blocker({
              category: 'unsupported_satisfied_finding',
              count: 1,
              affected_ids: ['ACCESS-1a'],
              summary: '1 practice(s) are marked SATISFIED with no accepted or edited evidence.',
            }),
          ],
        })}
        isLoading={false}
        isFinalized={false}
      />,
    )
    expect(screen.getByText(/2 item\(s\) to resolve/i)).toBeInTheDocument()
    expect(screen.getByText(/marked SATISFIED with no accepted/i)).toBeInTheDocument()
  })

  it('reports the true total when the id list is truncated', () => {
    // The service caps affected_ids but count stays exact, so the UI must
    // not imply the visible list is everything.
    render(
      <FinalizationChecklist
        readiness={readiness({
          blockers: [
            blocker({ count: 120, affected_ids: Array.from({ length: 50 }, (_, i) => `l${i}`) }),
          ],
        })}
        isLoading={false}
        isFinalized={false}
      />,
    )
    expect(screen.getByText(/and 112 more/)).toBeInTheDocument()
  })

  it('renders nothing once the assessment is finalized', () => {
    // A settled assessment must not simultaneously be described as
    // having outstanding work.
    const { container } = render(
      <FinalizationChecklist readiness={readiness()} isLoading={false} isFinalized />,
    )
    expect(container).toBeEmptyDOMElement()
  })
})
