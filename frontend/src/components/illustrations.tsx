import { useId } from 'react'

/**
 * Custom inline-SVG illustrations — one consistent line + soft-gradient style in
 * brand colours, dark-mode aware (strokes use currentColor; the gradient uses the
 * brand tokens). Subtle idle motion via the global `animate-*` keyframes, which
 * the prefers-reduced-motion guard in index.css neutralizes.
 *
 * Set the stroke tone with a text-* class on the wrapping element.
 */

interface Props {
  className?: string
}

function Gradient({ id }: { id: string }) {
  return (
    <defs>
      <linearGradient id={id} x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" style={{ stopColor: 'rgb(var(--c-brand-accent))' }} stopOpacity="0.9" />
        <stop offset="100%" style={{ stopColor: 'rgb(var(--c-brand))' }} stopOpacity="0.9" />
      </linearGradient>
    </defs>
  )
}

/** Calm "all clear" — nothing waiting / no escalations. */
export function IllustrationCalm({ className = '' }: Props) {
  const id = useId()
  return (
    <svg viewBox="0 0 120 100" className={`h-24 w-28 text-hairline ${className}`} fill="none" aria-hidden>
      <Gradient id={id} />
      <ellipse cx="60" cy="88" rx="34" ry="4" fill="currentColor" opacity="0.5" />
      <circle cx="60" cy="46" r="26" stroke={`url(#${id})`} strokeWidth="3" />
      <path
        d="M50 46l7 7 14-15"
        stroke={`url(#${id})`}
        strokeWidth="3.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="96" cy="22" r="3" className="animate-pulse" style={{ fill: 'rgb(var(--c-brand-accent))' }} />
      <circle cx="22" cy="30" r="2" fill="currentColor" />
    </svg>
  )
}

/** Empty list / empty queue. */
export function IllustrationEmptyList({ className = '' }: Props) {
  const id = useId()
  return (
    <svg viewBox="0 0 120 100" className={`h-24 w-28 text-hairline ${className}`} fill="none" aria-hidden>
      <Gradient id={id} />
      <ellipse cx="60" cy="88" rx="38" ry="4" fill="currentColor" opacity="0.5" />
      <rect x="30" y="20" width="60" height="56" rx="8" stroke="currentColor" strokeWidth="3" />
      <line x1="42" y1="38" x2="78" y2="38" stroke={`url(#${id})`} strokeWidth="3" strokeLinecap="round" />
      <line x1="42" y1="50" x2="70" y2="50" stroke="currentColor" strokeWidth="3" strokeLinecap="round" opacity="0.6" />
      <line x1="42" y1="62" x2="62" y2="62" stroke="currentColor" strokeWidth="3" strokeLinecap="round" opacity="0.4" />
    </svg>
  )
}

/** No displacements — a calendar with a check. */
export function IllustrationCalendar({ className = '' }: Props) {
  const id = useId()
  return (
    <svg viewBox="0 0 120 100" className={`h-24 w-28 text-hairline ${className}`} fill="none" aria-hidden>
      <Gradient id={id} />
      <ellipse cx="60" cy="88" rx="36" ry="4" fill="currentColor" opacity="0.5" />
      <rect x="28" y="22" width="64" height="54" rx="8" stroke="currentColor" strokeWidth="3" />
      <line x1="28" y1="36" x2="92" y2="36" stroke="currentColor" strokeWidth="3" />
      <line x1="42" y1="16" x2="42" y2="28" stroke={`url(#${id})`} strokeWidth="3" strokeLinecap="round" />
      <line x1="78" y1="16" x2="78" y2="28" stroke={`url(#${id})`} strokeWidth="3" strokeLinecap="round" />
      <path
        d="M48 56l8 8 16-18"
        stroke={`url(#${id})`}
        strokeWidth="3.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

/** 404 — a lost calendar block. */
export function Illustration404({ className = '' }: Props) {
  const id = useId()
  return (
    <svg viewBox="0 0 160 110" className={`h-28 w-40 text-hairline ${className}`} fill="none" aria-hidden>
      <Gradient id={id} />
      <ellipse cx="80" cy="98" rx="46" ry="5" fill="currentColor" opacity="0.5" />
      <text
        x="80"
        y="64"
        textAnchor="middle"
        fontSize="52"
        fontWeight="700"
        fill={`url(#${id})`}
        style={{ fontFamily: 'Geist Variable, sans-serif' }}
      >
        404
      </text>
      <rect x="30" y="18" width="100" height="70" rx="10" stroke="currentColor" strokeWidth="3" opacity="0.5" />
    </svg>
  )
}

/** Generic error. */
export function IllustrationError({ className = '' }: Props) {
  const id = useId()
  return (
    <svg viewBox="0 0 120 100" className={`h-24 w-28 text-hairline ${className}`} fill="none" aria-hidden>
      <Gradient id={id} />
      <ellipse cx="60" cy="90" rx="34" ry="4" fill="currentColor" opacity="0.5" />
      <path d="M60 20l34 58H26z" stroke={`url(#${id})`} strokeWidth="3" strokeLinejoin="round" />
      <line x1="60" y1="44" x2="60" y2="60" stroke={`url(#${id})`} strokeWidth="3.5" strokeLinecap="round" />
      <circle cx="60" cy="68" r="2.5" style={{ fill: 'rgb(var(--c-brand))' }} />
    </svg>
  )
}
