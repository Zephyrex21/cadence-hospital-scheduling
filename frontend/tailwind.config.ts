import type { Config } from 'tailwindcss'

/**
 * Cadence "Cream & Moon" design system (Apple-inspired).
 *
 * Palette values live as CSS variables in `src/styles/tokens.css` so light/dark
 * themes share one source of truth; this file maps them to Tailwind utilities.
 * Acuity colours (A1–A5) are always paired with a label + shape in the UI — never
 * conveyed by colour alone — for colourblind accessibility.
 */
const config: Config = {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  // acuityDotClass() builds `bg-acuity-N` dynamically (in the off-limits format.ts),
  // so these must be safelisted or Tailwind's JIT would purge them.
  safelist: [{ pattern: /^(bg|text|ring|border)-acuity-[1-5]$/ }],
  theme: {
    extend: {
      colors: {
        ink: 'rgb(var(--c-ink) / <alpha-value>)',
        slate: 'rgb(var(--c-slate) / <alpha-value>)',
        muted: 'rgb(var(--c-muted) / <alpha-value>)',
        hairline: 'rgb(var(--c-hairline) / <alpha-value>)',
        surface: 'rgb(var(--c-surface) / <alpha-value>)',
        elevated: 'rgb(var(--c-elevated) / <alpha-value>)',
        canvas: 'rgb(var(--c-canvas) / <alpha-value>)',
        scrim: 'rgb(var(--c-scrim) / <alpha-value>)',
        hero: 'rgb(var(--c-hero) / <alpha-value>)',
        brand: {
          DEFAULT: 'rgb(var(--c-brand) / <alpha-value>)',
          strong: 'rgb(var(--c-brand-strong) / <alpha-value>)',
          accent: 'rgb(var(--c-brand-accent) / <alpha-value>)',
          fill: 'rgb(var(--c-brand-fill) / <alpha-value>)',
        },
        'on-brand': 'rgb(var(--c-on-brand) / <alpha-value>)',
        success: 'rgb(var(--c-success) / <alpha-value>)',
        warning: 'rgb(var(--c-warning) / <alpha-value>)',
        danger: 'rgb(var(--c-danger) / <alpha-value>)',
        info: 'rgb(var(--c-info) / <alpha-value>)',
        acuity: {
          1: 'rgb(var(--c-acuity-1) / <alpha-value>)',
          2: 'rgb(var(--c-acuity-2) / <alpha-value>)',
          3: 'rgb(var(--c-acuity-3) / <alpha-value>)',
          4: 'rgb(var(--c-acuity-4) / <alpha-value>)',
          5: 'rgb(var(--c-acuity-5) / <alpha-value>)',
        },
      },
      backgroundImage: {
        // The Apple-blue "shine": lit from above, deeper at the base.
        'brand-gradient':
          'linear-gradient(180deg, rgb(var(--c-brand-accent)) 0%, rgb(var(--c-brand-fill)) 100%)',
        'brand-glow':
          'radial-gradient(60% 60% at 50% 0%, rgb(var(--c-brand-accent) / 0.16) 0%, transparent 70%)',
        sheen: 'linear-gradient(180deg, rgb(255 255 255 / 0.28) 0%, rgb(255 255 255 / 0) 55%)',
      },
      fontFamily: {
        // Real SF Pro on Apple devices; Inter (bundled, metrically close) elsewhere.
        sans: [
          '-apple-system',
          'BlinkMacSystemFont',
          'SF Pro Text',
          'Inter Variable',
          'Inter',
          'system-ui',
          'sans-serif',
        ],
        display: [
          '-apple-system',
          'BlinkMacSystemFont',
          'SF Pro Display',
          'Inter Variable',
          'Inter',
          'system-ui',
          'sans-serif',
        ],
        mono: ['ui-monospace', 'SF Mono', 'SFMono-Regular', 'Menlo', 'Consolas', 'monospace'],
      },
      fontSize: {
        'display-lg': ['3rem', { lineHeight: '1.05', letterSpacing: '-0.035em' }],
        display: ['2.25rem', { lineHeight: '1.1', letterSpacing: '-0.03em' }],
        title: ['1.625rem', { lineHeight: '1.2', letterSpacing: '-0.022em' }],
        headline: ['1.0625rem', { lineHeight: '1.3', letterSpacing: '-0.012em' }],
      },
      borderRadius: {
        control: '12px',
        card: '20px',
        modal: '28px',
        pill: '9999px',
      },
      boxShadow: {
        // Layered, warm-tinted shadows + a 1px top highlight (the "shine").
        xs: '0 1px 2px rgb(var(--shadow-rgb) / 0.06)',
        card: '0 1px 2px rgb(var(--shadow-rgb) / 0.04), 0 6px 18px -6px rgb(var(--shadow-rgb) / 0.10), inset 0 1px 0 var(--hl)',
        sm: '0 1px 2px rgb(var(--shadow-rgb) / 0.06), 0 3px 8px -2px rgb(var(--shadow-rgb) / 0.08)',
        md: '0 2px 4px rgb(var(--shadow-rgb) / 0.05), 0 12px 28px -8px rgb(var(--shadow-rgb) / 0.14)',
        lg: '0 8px 20px -6px rgb(var(--shadow-rgb) / 0.14), 0 32px 64px -16px rgb(var(--shadow-rgb) / 0.26)',
        raised:
          '0 4px 14px rgb(var(--shadow-rgb) / 0.10), 0 1px 3px rgb(var(--shadow-rgb) / 0.06), inset 0 1px 0 var(--hl)',
        'glow-brand':
          '0 0 0 1px rgb(var(--c-brand-fill) / 0.25), 0 10px 28px -8px rgb(var(--c-brand-fill) / 0.5)',
        'glow-success':
          '0 0 0 1px rgb(var(--c-success) / 0.35), 0 0 22px -6px rgb(var(--c-success) / 0.5)',
      },
      backdropBlur: {
        xs: '2px',
      },
      keyframes: {
        'fade-in': {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
        'fade-in-up': {
          from: { opacity: '0', transform: 'translateY(8px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'scale-in': {
          from: { opacity: '0', transform: 'translateY(4px) scale(0.97)' },
          to: { opacity: '1', transform: 'translateY(0) scale(1)' },
        },
        'slide-in-left': {
          from: { transform: 'translateX(-100%)' },
          to: { transform: 'translateX(0)' },
        },
        shimmer: {
          '100%': { transform: 'translateX(100%)' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-8px)' },
        },
        drift: {
          '0%, 100%': { transform: 'translate3d(0, 0, 0) scale(1)' },
          '50%': { transform: 'translate3d(2%, -3%, 0) scale(1.06)' },
        },
      },
      animation: {
        'fade-in': 'fade-in 150ms ease-out-soft both',
        'fade-in-up': 'fade-in-up 300ms ease-out-soft both',
        'scale-in': 'scale-in 200ms ease-out-soft both',
        'slide-in-left': 'slide-in-left 220ms ease-out-soft both',
        shimmer: 'shimmer 1.6s infinite',
        float: 'float 7s ease-in-out infinite',
        drift: 'drift 16s ease-in-out infinite',
      },
      transitionTimingFunction: {
        'ease-out-soft': 'cubic-bezier(0.16, 1, 0.3, 1)',
        'ease-spring': 'cubic-bezier(0.34, 1.56, 0.64, 1)',
      },
      transitionDuration: {
        250: '250ms',
        400: '400ms',
      },
    },
  },
  plugins: [],
}

export default config
