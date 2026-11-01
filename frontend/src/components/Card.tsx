import type { HTMLAttributes, ReactNode } from 'react'

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode
  /** Add default padding. Omit for cards that hold edge-to-edge tables/headers. */
  padded?: boolean
}

/** Surface card — catches light from above (hairline border + top highlight). */
export function Card({ children, padded = false, className = '', ...rest }: CardProps) {
  return (
    <div
      className={`rounded-card border border-hairline bg-surface shadow-card ${
        padded ? 'p-6' : ''
      } ${className}`}
      {...rest}
    >
      {children}
    </div>
  )
}

/** Optional card header with a hairline divider. */
export function CardHeader({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`border-b border-hairline px-6 py-4 ${className}`}>{children}</div>
}

export function CardTitle({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <h3 className={`font-display text-headline font-semibold text-ink ${className}`}>{children}</h3>
  )
}
