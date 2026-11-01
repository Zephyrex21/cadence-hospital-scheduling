import { CalendarBlank, Siren } from '../../components/icons'

/**
 * The login showcase: a calm, softly-lit day schedule with a walk-in emergency
 * sliding into a gap — the product metaphor in pure CSS/SVG (no WebGL, ~0 KB of
 * JS). Slow ambient orbs and a gentle float; all motion is neutralised by the
 * prefers-reduced-motion guard in index.css. Decorative only (aria-hidden).
 */
const ROWS = [
  { time: '9:00 am', name: 'Rajesh Kumar Verma', kind: 'General OPD', tone: 'plain' },
  { time: '9:30 am', name: 'Ananya Iyer', kind: 'Follow-up visit', tone: 'plain' },
  { time: '10:00 am', name: 'Harpreet Singh Gill', kind: 'A2 · Emergent', tone: 'emergency' },
  { time: '10:30 am', name: 'Mohammed Irfan Qureshi', kind: 'Moved 30 min later', tone: 'moved' },
] as const

export function HeroScene() {
  return (
    <div aria-hidden className="relative h-full w-full overflow-hidden bg-hero">
      {/* ambient light */}
      <div className="absolute -left-24 -top-28 h-[28rem] w-[28rem] rounded-full bg-brand-accent/25 blur-3xl animate-drift" />
      <div
        className="absolute -bottom-32 -right-20 h-[26rem] w-[26rem] rounded-full bg-warning/15 blur-3xl animate-drift"
        style={{ animationDelay: '-8s' }}
      />

      <div className="absolute inset-0 flex items-center justify-center p-10">
        <div className="glass w-full max-w-[26rem] rounded-modal border border-hairline p-5 shadow-lg animate-float">
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <span className="flex h-9 w-9 items-center justify-center rounded-control bg-brand/10 text-brand">
                <CalendarBlank size={20} weight="duotone" />
              </span>
              <div>
                <p className="text-[13px] font-semibold text-ink">Dr. Priya Sharma</p>
                <p className="text-xs text-muted">General Medicine · OPD</p>
              </div>
            </div>
            <span className="rounded-pill bg-ink/[0.06] px-2 py-0.5 text-[11px] font-semibold tracking-wide text-muted">
              IST
            </span>
          </div>

          <ul className="flex flex-col gap-2">
            {ROWS.map((r, i) => (
              <li
                key={r.time}
                className="flex items-center gap-3 animate-fade-in-up"
                style={{ animationDelay: `${i * 140 + 200}ms` }}
              >
                <span className="w-[4.25rem] shrink-0 text-right text-xs tabular-nums text-muted">
                  {r.time}
                </span>
                <div
                  className={`flex min-w-0 flex-1 items-center gap-2.5 rounded-control px-3 py-2.5 ${
                    r.tone === 'emergency'
                      ? 'btn-shine text-on-brand'
                      : r.tone === 'moved'
                        ? 'border border-dashed border-hairline bg-canvas/70'
                        : 'border border-hairline bg-surface shadow-xs'
                  }`}
                >
                  {r.tone === 'emergency' ? <Siren size={18} weight="fill" /> : null}
                  <div className="min-w-0">
                    <p
                      className={`truncate text-[13px] font-medium ${
                        r.tone === 'emergency' ? 'text-on-brand' : 'text-ink'
                      }`}
                    >
                      {r.name}
                    </p>
                    <p
                      className={`truncate text-xs ${
                        r.tone === 'emergency' ? 'text-on-brand/80' : 'text-muted'
                      }`}
                    >
                      {r.kind}
                    </p>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}
