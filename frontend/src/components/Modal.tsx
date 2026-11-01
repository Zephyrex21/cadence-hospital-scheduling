import { X } from './icons'
import { useEffect, useId, useRef } from 'react'
import type { ReactNode } from 'react'

interface ModalProps {
  title: string
  onClose: () => void
  children: ReactNode
  footer?: ReactNode
}

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), ' +
  'select:not([disabled]), [tabindex]:not([tabindex="-1"])'

/**
 * Accessible frosted-glass modal. Focus is moved in on open and trapped while open,
 * Escape and backdrop-click close it, body scroll is locked, and focus is restored
 * to the invoking element on unmount. The backdrop is the panel's *direct* parent
 * (the Modal.test contract) and enter animation is reduced-motion safe via index.css.
 */
export function Modal({ title, onClose, children, footer }: ModalProps) {
  const panelRef = useRef<HTMLDivElement>(null)
  const titleId = useId()

  useEffect(() => {
    const previouslyFocused = document.activeElement as HTMLElement | null
    const panel = panelRef.current

    function focusables(): HTMLElement[] {
      if (!panel) return []
      return Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
        (el) => el.offsetParent !== null,
      )
    }

    const initial = focusables()[0] ?? panel
    initial?.focus()

    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        e.preventDefault()
        onClose()
        return
      }
      if (e.key !== 'Tab') return
      const items = focusables()
      if (items.length === 0) {
        e.preventDefault()
        return
      }
      const first = items[0]
      const last = items[items.length - 1]
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', onKeyDown)
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.body.style.overflow = prevOverflow
      previouslyFocused?.focus?.()
    }
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-scrim/30 p-4 backdrop-blur-md animate-fade-in"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className="w-full max-w-lg overflow-hidden rounded-modal border border-hairline bg-elevated shadow-lg outline-none animate-scale-in max-h-[calc(100vh-2rem)] overflow-y-auto"
      >
        <div className="flex items-center justify-between gap-3 px-7 pb-2 pt-6">
          <h3 id={titleId} className="font-display text-title font-semibold text-ink">
            {title}
          </h3>
          <button
            onClick={onClose}
            aria-label="Close dialog"
            className="-mr-2 rounded-pill bg-ink/5 p-1.5 text-muted transition-colors duration-150 ease-out-soft hover:bg-ink/10 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/50"
          >
            <X size={16} weight="bold" />
          </button>
        </div>
        <div className="px-7 pb-6 pt-3">{children}</div>
        {footer && (
          <div className="flex justify-end gap-3 border-t border-hairline bg-canvas/60 px-7 py-4">
            {footer}
          </div>
        )}
      </div>
    </div>
  )
}
