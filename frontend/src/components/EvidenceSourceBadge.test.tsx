import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import EvidenceSourceBadge from './EvidenceSourceBadge'
import type { EvidenceReviewStatus, EvidenceSource } from '../api/types'

// NFR-4: "Every AI-proposed evidence mapping must be distinguishable from
// a human-confirmed one in both data model and UI." These are the two
// states that requirement is actually about — get them wrong and the
// platform's core trust proposition silently breaks.
describe('EvidenceSourceBadge', () => {
  it('labels an AI-proposed, pending-review link as such', () => {
    render(<EvidenceSourceBadge source="ai_proposed" reviewStatus="pending" />)
    expect(screen.getByText('AI-proposed')).toBeInTheDocument()
    expect(screen.getByText('Pending review')).toBeInTheDocument()
  })

  it('labels a manually-linked, accepted link as manual, not AI-proposed', () => {
    render(<EvidenceSourceBadge source="manual" reviewStatus="accepted" />)
    expect(screen.getByText('Manual')).toBeInTheDocument()
    expect(screen.queryByText('AI-proposed')).not.toBeInTheDocument()
  })

  it.each<[EvidenceSource, EvidenceReviewStatus, string]>([
    ['ai_proposed', 'accepted', 'Accepted'],
    ['ai_proposed', 'edited', 'Edited'],
    ['ai_proposed', 'rejected', 'Rejected'],
  ])('still shows the AI-proposed origin after review (%s/%s)', (source, reviewStatus, expectedLabel) => {
    render(<EvidenceSourceBadge source={source} reviewStatus={reviewStatus} />)
    expect(screen.getByText('AI-proposed')).toBeInTheDocument()
    expect(screen.getByText(expectedLabel)).toBeInTheDocument()
  })
})
