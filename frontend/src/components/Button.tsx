import type { ButtonHTMLAttributes, ReactNode } from 'react'

import { Loader2 } from './icons'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'
type Size = 'sm' | 'md' | 'lg'

const base =
  'relative inline-flex select-none items-center justify-center gap-2 rounded-pill font-medium ' +
  'transition-[color,background-color,box-shadow,transform,filter] duration-200 ease-out-soft ' +
  'active:scale-[0.97] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/60 ' +
  'focus-visible:ring-offset-2 focus-visible:ring-offset-surface ' +
  'disabled:cursor-not-allowed disabled:opacity-55 disabled:active:scale-100'

// Primary is the Apple-blue "shine" face (see .btn-shine in index.css). Destructive
// actions are a soft tinted pill so they never out-shout the primary action.
const variants: Record<Variant, string> = {
  primary: 'btn-shine text-on-brand',
  secondary:
    'bg-surface text-ink shadow-xs ring-1 ring-inset ring-hairline hover:bg-canvas hover:shadow-sm',
  ghost: 'text-slate hover:bg-ink/5 hover:text-ink',
  danger: 'bg-danger/10 text-danger ring-1 ring-inset ring-danger/25 hover:bg-danger/15',
}

const sizes: Record<Size, string> = {
  sm: 'h-8 px-3.5 text-xs',
  md: 'h-10 px-5 text-sm',
  lg: 'h-12 px-6 text-[15px]',
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
