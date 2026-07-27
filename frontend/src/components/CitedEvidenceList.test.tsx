import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import CitedEvidenceList from './CitedEvidenceList'
import type { EvidenceCitation } from '../api/types'

// ADR-0040 computed cited_evidence server-side; ADR-0051 is what finally
// renders it on the Dashboard tab. These tests are the real assertion
// that the closed gap stays closed.
describe('CitedEvidenceList', () => {
  it('renders nothing for a gap with no cited evidence', () => {
    const { container } = render(<CitedEvidenceList citations={[]} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders a citation with its document id and review status', () => {
    const citation: EvidenceCitation = {
      evidence_link_id: 'link-1',
      document_id: 'doc-incident-report',
      review_status: 'rejected',
      is_superseded: false,
    }
    render(<CitedEvidenceList citations={[citation]} />)
    expect(screen.getByText('doc-incident-report')).toBeInTheDocument()
    expect(screen.getByText('Rejected')).toBeInTheDocument()
    expect(screen.queryByText('⚠ document superseded')).not.toBeInTheDocument()
  })

  it('flags a citation whose document has been superseded', () => {
    const citation: EvidenceCitation = {
      evidence_link_id: 'link-1',
      document_id: 'doc-old-policy',
      review_status: 'accepted',
      is_superseded: true,
    }
    render(<CitedEvidenceList citations={[citation]} />)
    expect(screen.getByText('⚠ document superseded')).toBeInTheDocument()
  })

  it('renders multiple citations for the same gap', () => {
    const citations: EvidenceCitation[] = [
      { evidence_link_id: 'link-1', document_id: 'doc-a', review_status: 'rejected', is_superseded: false },
      { evidence_link_id: 'link-2', document_id: 'doc-b', review_status: 'pending', is_superseded: false },
    ]
    render(<CitedEvidenceList citations={citations} />)
    expect(screen.getByText('doc-a')).toBeInTheDocument()
    expect(screen.getByText('doc-b')).toBeInTheDocument()
    expect(screen.getByText('Pending review')).toBeInTheDocument()
  })
})
