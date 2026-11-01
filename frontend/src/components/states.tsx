import { Loader2 } from './icons'
import type { ReactNode } from 'react'

import { Button } from './Button'
import { IllustrationError } from './illustrations'

/**
 * Shared async-state primitives so every data view presents loading, empty, and
 * error identically. Loading announces via role="status" (polite); errors via
 * role="alert" (assertive).
 */

export function Spinner({ className = 'h-4 w-4' }: { className?: string }) {
  return <Loader2 className={`animate-spin ${className}`} aria-hidden />
}

export function LoadingState({ label = 'Loading…' }: { label?: string }) {
  return (
    <div
      role="status"
      className="flex items-center justify-center gap-2 p-10 text-sm text-muted animate-fade-in"
    >
      <Spinner />
      <span>{label}</span>
    </div>
  )
}

export function ErrorState({
  label = 'Something went wrong.',
  onRetry,
}: {
  label?: string
  onRetry?: () => void
}) {
  return (
    <div
      role="alert"
      className="flex flex-col items-center gap-3 p-10 text-center text-sm text-danger animate-fade-in"
    >
      <IllustrationError />
      <span>{label}</span>
      {onRetry && (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  )
}

export function EmptyState({
  icon,
  title,
  hint,
}: {
  icon?: ReactNode
  title: string
  hint?: string
}) {
  return (
    <div className="flex flex-col items-center gap-3 p-10 text-center animate-fade-in">
      {icon && (
        <div className="text-muted" aria-hidden>
          {icon}
        </div>
      )}
      <p className="text-sm font-medium text-ink">{title}</p>
      {hint && <p className="max-w-sm text-xs text-muted">{hint}</p>}
    </div>
  )
}
