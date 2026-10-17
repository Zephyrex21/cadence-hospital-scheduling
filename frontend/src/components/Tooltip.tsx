import { useId, useState, type KeyboardEvent, type ReactNode } from 'react'

/**
 * Lightweight accessible tooltip (top placement). Shows on hover and keyboard
 * focus, dismisses on Escape, and is announced via aria-describedby. `bg-ink` /
 * `text-surface` flip with the theme so the bubble is always high-contrast.
 */
export function Tooltip({ label, children }: { label: string; children: ReactNode }) {
  const [open, setOpen] = useState(false)
  const id = useId()
  return (
    <span
      className="relative inline-flex"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
      onKeyDown={(e: KeyboardEvent) => {
        if (e.key === 'Escape') setOpen(false)
      }}
    >
      <span aria-describedby={open ? id : undefined} className="inline-flex">
        {children}
      </span>
      {open && (
        <span
          role="tooltip"
          id={id}
          className="pointer-events-none absolute bottom-full left-1/2 z-[70] mb-2 -translate-x-1/2 whitespace-nowrap rounded-control bg-ink px-2 py-1 text-xs font-medium text-surface shadow-md animate-fade-in"
        >
          {label}
        </span>
      )}
    </span>
  )
}
