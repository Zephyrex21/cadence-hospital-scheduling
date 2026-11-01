/**
 * The Cadence mark: a rounded "C" holding a heartbeat line, on an Apple-blue
 * squircle lit from above. Pure SVG — no font, crisp at any size.
 */
export function BrandMark({ size = 36, className = '' }: { size?: number; className?: string }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center bg-brand-gradient shadow-glow-brand ${className}`}
      style={{ width: size, height: size, borderRadius: size * 0.3 }}
      aria-hidden
    >
      <svg viewBox="0 0 32 32" width={size * 0.64} height={size * 0.64} fill="none">
        <path
          d="M23.2 10.4A9.2 9.2 0 1 0 23.2 21.6"
          stroke="white"
          strokeWidth="2.7"
          strokeLinecap="round"
        />
        <path
          d="M10.6 16.4h2.7l1.7-3.9 2.6 7.4 1.8-3.5h1.6"
          stroke="white"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </span>
  )
}
