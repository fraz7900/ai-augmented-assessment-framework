import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import DocumentPicker from './DocumentPicker'
import type { DocumentSummary } from '../api/types'

function doc(overrides: Partial<DocumentSummary> = {}): DocumentSummary {
  return {
    id: 'doc-1',
    filename: 'access_policy.pdf',
    file_type: 'pdf',
    submitter: null,
    uploaded_at: '2026-08-16T12:00:00Z',
    is_superseded: false,
    parser_version: 'pypdf==6.16.0',
    ...overrides,
  }
}

// This component replaced a bare text input whose placeholder was "from
// Upload" -- the reviewer had to copy a UUID between screens by hand.
// These tests pin the three states apart, because "loading" and "you
// have no documents" rendering identically is the dead end that made the
// old flow confusing.
describe('DocumentPicker', () => {
  it('says it is loading rather than looking empty', () => {
    render(<DocumentPicker documents={undefined} isLoading value="" onChange={() => {}} />)
    expect(screen.getByText(/loading documents/i)).toBeInTheDocument()
  })

  it('tells the user what to do when nothing has been ingested', () => {
    render(<DocumentPicker documents={[]} isLoading={false} value="" onChange={() => {}} />)
    // An empty dropdown with no explanation is the failure this avoids.
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
    expect(screen.getByText(/no documents ingested yet/i)).toBeInTheDocument()
    expect(screen.getByText(/Upload/)).toBeInTheDocument()
  })

  it('lists documents by filename, not by id', () => {
    render(
      <DocumentPicker
        documents={[doc(), doc({ id: 'doc-2', filename: 'incident_plan.pdf' })]}
        isLoading={false}
        value=""
        onChange={() => {}}
      />,
    )
    expect(screen.getByRole('option', { name: /access_policy\.pdf/ })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /incident_plan\.pdf/ })).toBeInTheDocument()
  })

  it('reports the chosen document id to its parent', () => {
    const onChange = vi.fn()
    render(
      <DocumentPicker
        documents={[doc(), doc({ id: 'doc-2', filename: 'incident_plan.pdf' })]}
        isLoading={false}
        value=""
        onChange={onChange}
      />,
    )
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'doc-2' } })
    expect(onChange).toHaveBeenCalledWith('doc-2')
  })

  it('disambiguates documents that share a filename', () => {
    // Re-uploading the same file is how you correct a bad ingest, and a
    // slow synchronous upload invites a retry, so same-name copies are
    // common. Labelling them by filename and date alone made them
    // indistinguishable — worse than the UUID box this replaced, where
    // at least the ids differed.
    render(
      <DocumentPicker
        documents={[
          doc({ id: 'aaaaaaaa-1111', uploaded_at: '2026-08-16T18:21:00Z' }),
          doc({ id: 'bbbbbbbb-2222', uploaded_at: '2026-08-16T19:38:00Z' }),
        ]}
        isLoading={false}
        value=""
        onChange={() => {}}
      />,
    )
    const options = screen.getAllByRole('option').filter((o) => o.textContent?.includes('.pdf'))
    expect(options).toHaveLength(2)
    // Each carries a distinct short id, so they are actually tellable apart.
    expect(options[0].textContent).toContain('aaaaaaaa')
    expect(options[1].textContent).toContain('bbbbbbbb')
    expect(options[0].textContent).not.toEqual(options[1].textContent)
    expect(screen.getByText(/share a filename/i)).toBeInTheDocument()
  })

  it('does not clutter labels when every filename is unique', () => {
    // The disambiguator is opt-in on duplication; the common case stays
    // readable rather than every row carrying a hex fragment.
    render(
      <DocumentPicker
        documents={[doc(), doc({ id: 'doc-2', filename: 'incident_plan.pdf' })]}
        isLoading={false}
        value=""
        onChange={() => {}}
      />,
    )
    expect(screen.getByRole('option', { name: /access_policy\.pdf/ }).textContent).not.toMatch(
      /doc-1/,
    )
    expect(screen.queryByText(/share a filename/i)).not.toBeInTheDocument()
  })

  it('warns when the selected document has been superseded', () => {
    // ADR-0050: citing a policy that has since been replaced is a real
    // review error, so the chooser has to say so at selection time.
    render(
      <DocumentPicker
        documents={[doc({ is_superseded: true })]}
        isLoading={false}
        value="doc-1"
        onChange={() => {}}
      />,
    )
    expect(screen.getByText(/newer document has replaced this one/i)).toBeInTheDocument()
  })

  it('does not warn about supersession for a current document', () => {
    render(
      <DocumentPicker documents={[doc()]} isLoading={false} value="doc-1" onChange={() => {}} />,
    )
    expect(screen.queryByText(/newer document has replaced/i)).not.toBeInTheDocument()
  })
})
