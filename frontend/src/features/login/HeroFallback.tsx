/**
 * Static hero shown instead of the 3D scene on reduced-motion, no-WebGL, or small
 * screens, and as the Suspense fallback while the 3D chunk loads. Same metaphor —
 * frosted "time blocks" with one accent block slotted into the day — in pure CSS/SVG.
 */
export function HeroFallback() {
  return (
    <div className="relative h-full w-full overflow-hidden">
      <div className="absolute inset-0 bg-brand-gradient opacity-90" />
      <div className="absolute inset-0 bg-brand-glow" />
      <div className="absolute inset-0 flex items-center justify-center p-12">
        <div className="flex w-full max-w-sm flex-col gap-3">
          {[0, 1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-12 rounded-card border border-white/20 bg-white/10 backdrop-blur-sm"
              style={{ marginLeft: `${(i % 2) * 12}px`, width: `${86 - (i % 3) * 8}%` }}
            />
          ))}
          <div className="h-12 w-[70%] translate-x-6 rounded-card border border-white/40 bg-white/25 shadow-lg backdrop-blur-md" />
        </div>
      </div>
    </div>
  )
}
