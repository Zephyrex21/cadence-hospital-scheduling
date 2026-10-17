/** Shimmer skeleton placeholder. Decorative — wrap the loading region in an
 *  element with aria-busy / role="status" so the shimmer itself stays silent. */
export function Skeleton({ className = '' }: { className?: string }) {
  return (
    <div className={`relative overflow-hidden rounded-control bg-hairline/50 ${className}`}>
      <div className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-surface/70 to-transparent animate-shimmer" />
    </div>
  )
}

/** Placeholder grid for a table that is still loading. */
export function TableSkeleton({ rows = 6, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <div className="flex flex-col gap-3 p-5" role="status" aria-busy aria-label="Loading">
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="flex gap-4">
          {Array.from({ length: cols }).map((_, c) => (
            <Skeleton key={c} className="h-4 flex-1" />
          ))}
        </div>
      ))}
    </div>
  )
}
