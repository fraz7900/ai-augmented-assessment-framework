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
      text_provenance: 'exact',
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
      text_provenance: 'exact',
    }
    render(<CitedEvidenceList citations={[citation]} />)
    expect(screen.getByText('⚠ document superseded')).toBeInTheDocument()
  })

  it('renders multiple citations for the same gap', () => {
    const citations: EvidenceCitation[] = [
      { evidence_link_id: 'link-1', document_id: 'doc-a', review_status: 'rejected', is_superseded: false, text_provenance: 'exact' },
      { evidence_link_id: 'link-2', document_id: 'doc-b', review_status: 'pending', is_superseded: false, text_provenance: 'exact' },
    ]
    render(<CitedEvidenceList citations={citations} />)
    expect(screen.getByText('doc-a')).toBeInTheDocument()
    expect(screen.getByText('doc-b')).toBeInTheDocument()
    expect(screen.getByText('Pending review')).toBeInTheDocument()
  })
})

// ADR-0076: the same provenance the chat tab shows, on the citations the
// dashboard renders and the exports print. ADR-0074 shipped this only
// where evidence is quoted verbatim and disclosed that everywhere else
// had nothing.

describe('CitedEvidenceList text provenance', () => {
  const base = {
    evidence_link_id: 'link-1',
    document_id: 'doc-a',
    review_status: 'accepted',
    is_superseded: false,
  } as const

  it('flags a citation whose evidence was recovered by OCR', () => {
    render(<CitedEvidenceList citations={[{ ...base, text_provenance: 'ocr' }]} />)
    expect(screen.getByText('OCR — approximate')).toBeInTheDocument()
  })

  it('says nothing for evidence read from a real text layer', () => {
    // The mostly-exact document case. A note on every ordinary citation
    // is noise, and noise is what stops anyone reading the one that
    // matters.
    render(<CitedEvidenceList citations={[{ ...base, text_provenance: 'exact' }]} />)
    expect(screen.queryByText(/OCR/)).not.toBeInTheDocument()
    expect(screen.queryByText(/provenance/)).not.toBeInTheDocument()
  })

  it('shows provenance and supersession together when both apply', () => {
    // They are independent facts about a citation: one is about where
    // the text came from, the other about whether the document has been
    // replaced. A reviewer needs both.
    render(
      <CitedEvidenceList
        citations={[{ ...base, is_superseded: true, text_provenance: 'ocr' }]}
      />,
    )
    expect(screen.getByText('OCR — approximate')).toBeInTheDocument()
    expect(screen.getByText(/document superseded/)).toBeInTheDocument()
  })
})
