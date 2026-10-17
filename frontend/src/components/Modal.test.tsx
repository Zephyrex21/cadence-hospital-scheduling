import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { Modal } from './Modal'

describe('Modal', () => {
  it('renders as a labelled, modal dialog', () => {
    render(
      <Modal title="Book appointment" onClose={() => {}}>
        body
      </Modal>,
    )
    const dialog = screen.getByRole('dialog')
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(dialog).toHaveAccessibleName('Book appointment')
  })

  it('closes on Escape', () => {
    const onClose = vi.fn()
    render(
      <Modal title="T" onClose={onClose}>
        body
      </Modal>,
    )
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('closes when the close button is pressed', () => {
    const onClose = vi.fn()
    render(
      <Modal title="T" onClose={onClose}>
        body
      </Modal>,
    )
    fireEvent.click(screen.getByLabelText('Close dialog'))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('closes when the backdrop is clicked but not when the panel is', () => {
    const onClose = vi.fn()
    render(
      <Modal title="T" onClose={onClose}>
        body
      </Modal>,
    )
    const dialog = screen.getByRole('dialog')
    fireEvent.mouseDown(dialog)
    expect(onClose).not.toHaveBeenCalled()

    const backdrop = dialog.parentElement as HTMLElement
    fireEvent.mouseDown(backdrop)
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('restores body scroll after unmount', () => {
    const { unmount } = render(
      <Modal title="T" onClose={() => {}}>
        body
      </Modal>,
    )
    expect(document.body.style.overflow).toBe('hidden')
    unmount()
    expect(document.body.style.overflow).toBe('')
  })
})
