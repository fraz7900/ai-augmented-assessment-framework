import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import DetachDocumentButton from './DetachDocumentButton'
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

function renderButton(props: Partial<Parameters<typeof DetachDocumentButton>[0]> = {}) {
  const onDetach = vi.fn()
  render(
    <DetachDocumentButton
      document={doc()}
      isSubmitting={false}
      error={null}
      onDetach={onDetach}
      {...props}
    />,
  )
  return { onDetach }
}

describe('DetachDocumentButton', () => {
  it('names the document it will remove', () => {
    // Acting on the picker's selection, so the button has to say which
    // document that is — "Remove document" beside a dropdown is a way
    // to detach the wrong one.
    renderButton()
    expect(
      screen.getByRole('button', { name: /remove access_policy\.pdf from this assessment/i }),
    ).toBeInTheDocument()
  })

  it('offers nothing when no document is selected', () => {
    renderButton({ document: undefined })
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('detaches the selected document', () => {
    const { onDetach } = renderButton()
    fireEvent.click(screen.getByRole('button', { name: /remove/i }))
    expect(onDetach).toHaveBeenCalledWith('doc-1')
  })

  it('shows the server refusal verbatim when evidence still cites it', () => {
    // The interesting case. The server's message names the count and
    // what to do about it, which is more use than anything this
    // component could say instead.
    renderButton({
      error: new Error(
        "Document 'doc-1' is still cited by 3 evidence link(s). Reject or remove them before "
          + 'detaching it.',
      ),
    })
    expect(screen.getByText(/still cited by 3 evidence link\(s\)/i)).toBeInTheDocument()
  })

  it('disables itself while the request is in flight', () => {
    renderButton({ isSubmitting: true })
    expect(screen.getByRole('button', { name: /removing/i })).toBeDisabled()
  })

  it('renders nothing once the assessment is finalized', () => {
    renderButton({ isDisabled: true })
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})
