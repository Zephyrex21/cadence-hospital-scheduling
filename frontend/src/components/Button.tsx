import { Loader2 } from 'lucide-react'
import type { ButtonHTMLAttributes, ReactNode } from 'react'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'
type Size = 'sm' | 'md' | 'lg'

const base =
  'relative inline-flex items-center justify-center gap-2 rounded-control font-medium ' +
  'transition-[color,background-color,box-shadow,transform] duration-150 ease-out-soft ' +
  'active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/50 ' +
  'focus-visible:ring-offset-2 focus-visible:ring-offset-surface ' +
  'disabled:cursor-not-allowed disabled:opacity-60 disabled:active:scale-100'

// `text-surface` (not a literal white) flips with the theme: on the light-teal brand
// of dark mode it renders dark text, keeping AA contrast in both themes.
const variants: Record<Variant, string> = {
  primary: 'bg-brand text-surface shadow-sm hover:bg-brand-strong',
  secondary: 'bg-surface text-ink ring-1 ring-inset ring-hairline hover:bg-canvas',
  ghost: 'text-slate hover:bg-canvas hover:text-ink',
  danger: 'bg-danger text-surface shadow-sm hover:bg-danger/90',
}

const sizes: Record<Size, string> = {
  sm: 'h-8 px-3 text-xs',
  md: 'h-10 px-4 text-sm',
  lg: 'h-11 px-5 text-sm',
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  loading?: boolean
  children: ReactNode
}

export function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  className = '',
  children,
  disabled,
  ...rest
}: ButtonProps) {
  return (
    <button
      className={`${base} ${variants[variant]} ${sizes[size]} ${className}`}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading && <Loader2 size={16} className="animate-spin" aria-hidden />}
      {children}
    </button>
  )
}
