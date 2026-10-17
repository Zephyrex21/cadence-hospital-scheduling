import { Monitor, Moon, Sun } from 'lucide-react'

import { type Theme, useTheme } from './ThemeProvider'

const OPTIONS: { value: Theme; icon: typeof Sun; label: string }[] = [
  { value: 'light', icon: Sun, label: 'Light' },
  { value: 'system', icon: Monitor, label: 'System' },
  { value: 'dark', icon: Moon, label: 'Dark' },
]

/** Compact segmented theme control (system / light / dark). */
export function ThemeToggle() {
  const { theme, setTheme } = useTheme()
  return (
    <div
      role="radiogroup"
      aria-label="Theme"
      className="inline-flex items-center gap-0.5 rounded-pill border border-hairline bg-surface/70 p-0.5 backdrop-blur"
    >
      {OPTIONS.map(({ value, icon: Icon, label }) => {
        const active = theme === value
        return (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={active}
            aria-label={label}
            title={label}
            onClick={() => setTheme(value)}
            className={`inline-flex h-7 w-7 items-center justify-center rounded-pill transition-colors duration-150 ease-out-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/50 ${
              active ? 'bg-brand text-surface shadow-xs' : 'text-muted hover:text-ink'
            }`}
          >
            <Icon size={15} aria-hidden />
          </button>
        )
      })}
    </div>
  )
}
