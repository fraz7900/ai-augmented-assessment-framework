import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import FrameworkVersionSelect from './FrameworkVersionSelect'

// ADR-0053 built the multi-version registry and disclosed that no screen
// reached it. These tests are the assertion that the closed gap stays
// closed, and that each of the three states stays visually distinct.
describe('FrameworkVersionSelect', () => {
  it('renders nothing before versions have loaded', () => {
    const { container } = render(
      <FrameworkVersionSelect versions={undefined} value="" onChange={() => {}} />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('renders nothing for an unrecognised framework', () => {
    // The endpoint answers [] rather than 404 for an unknown name, so an
    // empty list is a real answer and must not render an empty control.
    const { container } = render(
      <FrameworkVersionSelect versions={[]} value="" onChange={() => {}} />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('shows a plain label, not a dropdown, when only one version exists', () => {
    // The state every framework in this project is in today.
    render(<FrameworkVersionSelect versions={['2.1']} value="" onChange={() => {}} />)
    expect(screen.getByTestId('framework-version-single')).toHaveTextContent('2.1')
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
  })

  it('offers a real choice when more than one version exists, defaulting to latest', () => {
    render(<FrameworkVersionSelect versions={['2.0', '2.1']} value="" onChange={() => {}} />)
    const select = screen.getByRole('combobox')
    expect(select).toHaveValue('')
    expect(screen.getByRole('option', { name: 'Latest (2.1)' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: '2.0' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: '2.1' })).toBeInTheDocument()
  })

  it('reports an explicitly pinned version to its parent', () => {
    const onChange = vi.fn()
    render(<FrameworkVersionSelect versions={['2.0', '2.1']} value="" onChange={onChange} />)
    fireEvent.change(screen.getByRole('combobox'), { target: { value: '2.0' } })
    expect(onChange).toHaveBeenCalledWith('2.0')
  })
})
