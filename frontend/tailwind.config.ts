import type { Config } from 'tailwindcss'

/**
 * Cadence "Clinical Calm 2.0" design system.
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
        },
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
        'brand-gradient':
          'linear-gradient(135deg, rgb(var(--c-brand-strong)) 0%, rgb(var(--c-brand)) 45%, rgb(var(--c-brand-accent)) 100%)',
        'brand-glow':
          'radial-gradient(60% 60% at 50% 0%, rgb(var(--c-brand-accent) / 0.18) 0%, transparent 70%)',
      },
      fontFamily: {
        sans: ['Inter Variable', 'Inter', 'system-ui', 'sans-serif'],
        display: ['Geist Variable', 'Geist', 'Inter Variable', 'system-ui', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Consolas', 'monospace'],
      },
      fontSize: {
        'display-lg': ['2.5rem', { lineHeight: '1.1', letterSpacing: '-0.02em' }],
        display: ['2rem', { lineHeight: '1.15', letterSpacing: '-0.02em' }],
        title: ['1.375rem', { lineHeight: '1.25', letterSpacing: '-0.01em' }],
      },
      borderRadius: {
        control: '8px',
        card: '14px',
        modal: '20px',
        pill: '9999px',
      },
      boxShadow: {
        xs: '0 1px 2px rgb(15 23 42 / 0.05)',
        card: '0 1px 2px rgb(15 23 42 / 0.04), 0 1px 3px rgb(15 23 42 / 0.06)',
        sm: '0 1px 2px rgb(15 23 42 / 0.04), 0 2px 6px rgb(15 23 42 / 0.06)',
        md: '0 2px 4px rgb(15 23 42 / 0.05), 0 8px 20px -4px rgb(15 23 42 / 0.10)',
        lg: '0 8px 16px -4px rgb(15 23 42 / 0.10), 0 24px 48px -12px rgb(15 23 42 / 0.18)',
        raised: '0 4px 12px rgb(15 23 42 / 0.08), 0 2px 4px rgb(15 23 42 / 0.04)',
        'glow-brand': '0 0 0 1px rgb(var(--c-brand) / 0.25), 0 10px 30px -8px rgb(var(--c-brand) / 0.45)',
        'glow-success': '0 0 0 1px rgb(var(--c-success) / 0.35), 0 0 22px -6px rgb(var(--c-success) / 0.5)',
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
          from: { opacity: '0', transform: 'translateY(4px) scale(0.98)' },
          to: { opacity: '1', transform: 'translateY(0) scale(1)' },
        },
        'slide-in-left': {
          from: { transform: 'translateX(-100%)' },
          to: { transform: 'translateX(0)' },
        },
        shimmer: {
          '100%': { transform: 'translateX(100%)' },
        },
      },
      animation: {
        'fade-in': 'fade-in 150ms ease-out-soft both',
        'fade-in-up': 'fade-in-up 250ms ease-out-soft both',
        'scale-in': 'scale-in 180ms ease-out-soft both',
        'slide-in-left': 'slide-in-left 200ms ease-out-soft both',
        shimmer: 'shimmer 1.6s infinite',
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
