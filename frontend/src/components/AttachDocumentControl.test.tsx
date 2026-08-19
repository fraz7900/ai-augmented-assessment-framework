import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import AttachDocumentControl from './AttachDocumentControl'
import type { DocumentSummary } from '../api/types'

function doc(overrides: Partial<DocumentSummary> = {}): DocumentSummary {
  return {
    id: 'doc-1',
    filename: 'access_policy.pdf',
    file_type: 'pdf',
    submitter: null,
    uploaded_at: '2026-08-19T12:00:00Z',
    is_superseded: false,
    parser_version: 'pypdf==6.16.0',
    ...overrides,
  }
}

function open(props: Partial<Parameters<typeof AttachDocumentControl>[0]> = {}) {
  const onAttach = vi.fn()
  render(
    <AttachDocumentControl
      allDocuments={[doc()]}
      attachedIds={[]}
      onAttach={onAttach}
      {...props}
    />,
  )
  fireEvent.click(screen.getByRole('button', { name: /attach a document/i }))
  return { onAttach }
}

// Attaching is the deliberate step across the line the scoped chooser
// draws (ADR-0062): the picker shows only this assessment's documents,
// and this is how one gets there.
describe('AttachDocumentControl', () => {
  it('offers a document that is not attached yet', () => {
    open()
    expect(screen.getByRole('option', { name: /access_policy\.pdf/ })).toBeInTheDocument()
  })

  it('does not offer a document already attached to this assessment', () => {
    open({ attachedIds: ['doc-1'] })
    expect(screen.queryByRole('option', { name: /access_policy\.pdf/ })).not.toBeInTheDocument()
    expect(screen.getByText(/already attached/i)).toBeInTheDocument()
  })

  it('tells "nothing ingested" apart from "everything already attached"', () => {
    // An empty dropdown with no explanation reads as broken — the same
    // distinction DocumentPicker draws, for the same reason.
    open({ allDocuments: [] })
    expect(screen.getByText(/no documents have been ingested/i)).toBeInTheDocument()
  })

  it('attaches the chosen document', () => {
    const { onAttach } = open()
    fireEvent.change(screen.getByLabelText(/document to attach/i), {
      target: { value: 'doc-1' },
    })
    fireEvent.click(screen.getByRole('button', { name: /^attach$/i }))
    expect(onAttach).toHaveBeenCalledWith('doc-1')
  })

  it('will not attach until something is chosen', () => {
    open()
    expect(screen.getByRole('button', { name: /^attach$/i })).toBeDisabled()
  })

  it('flags a superseded document rather than hiding it', () => {
    // ADR-0050: superseded is a warning, not a disqualification — a
    // reviewer may legitimately be assessing the older version.
    open({ allDocuments: [doc({ is_superseded: true })] })
    expect(screen.getByRole('option', { name: /superseded/ })).toBeInTheDocument()
  })

  it('renders nothing at all once the assessment is finalized', () => {
    render(
      <AttachDocumentControl
        allDocuments={[doc()]}
        attachedIds={[]}
        isDisabled
        onAttach={vi.fn()}
      />,
    )
    expect(screen.queryByRole('button', { name: /attach a document/i })).not.toBeInTheDocument()
  })
})
