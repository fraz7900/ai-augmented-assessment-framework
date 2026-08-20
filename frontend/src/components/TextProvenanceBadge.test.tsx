import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import TextProvenanceBadge from './TextProvenanceBadge'

// R-33 (ADR-0074). The badge exists so a reviewer reading a quotation
// knows whether the wording can be trusted character-for-character. The
// tests are about the distinctions it must not collapse.

describe('TextProvenanceBadge', () => {
  it('renders nothing for exact text', () => {
    // A badge on every ordinary quotation is noise, and noise is what
    // makes people stop reading the badge that matters.
    const { container } = render(<TextProvenanceBadge provenance="exact" />)
    expect(container).toBeEmptyDOMElement()
  })

  it('warns plainly when the passage itself was recognised', () => {
    render(<TextProvenanceBadge provenance="ocr" />)
    expect(screen.getByText('OCR — approximate')).toBeInTheDocument()
  })

  it('hedges differently when it cannot say for this passage', () => {
    // "This is approximate" and "this might be approximate" are
    // different claims; a reviewer acts on them differently.
    render(<TextProvenanceBadge provenance="possibly_ocr" />)
    expect(screen.getByText('may be OCR')).toBeInTheDocument()
    expect(screen.queryByText('OCR — approximate')).not.toBeInTheDocument()
  })

  it('does not present an absent record as a clean one', () => {
    render(<TextProvenanceBadge provenance="unknown" />)
    expect(screen.getByText('provenance unrecorded')).toBeInTheDocument()
  })

  it('explains what to do about it, not just what happened', () => {
    render(<TextProvenanceBadge provenance="ocr" />)
    expect(screen.getByTitle(/Check it against the source page/)).toBeInTheDocument()
  })

  it('says why an unrecorded provenance is not reassurance', () => {
    render(<TextProvenanceBadge provenance="unknown" />)
    expect(
      screen.getByTitle(/Absence of a record is not evidence of an intact text layer/),
    ).toBeInTheDocument()
  })

  it('gives the three non-exact states visibly different treatments', () => {
    // If two of them ever render identically the distinction is
    // decorative rather than real.
    const labels = (['ocr', 'possibly_ocr', 'unknown'] as const).map((provenance) => {
      const { container, unmount } = render(<TextProvenanceBadge provenance={provenance} />)
      const text = container.textContent
      unmount()
      return text
    })
    expect(new Set(labels).size).toBe(3)
  })
})
