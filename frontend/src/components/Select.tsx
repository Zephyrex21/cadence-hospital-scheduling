import { ChevronDown } from 'lucide-react'
import { forwardRef, type ReactNode, type SelectHTMLAttributes } from 'react'

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string
  error?: string
  children: ReactNode
}

/**
 * A styled **native** <select> (keeps `selectOption` / react-hook-form `register`
 * working) with a custom chevron. forwardRef so RHF can wire it up.
 */
export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { label, error, id, className = '', children, ...rest },
  ref,
) {
  const selectId = id ?? rest.name
  const errorId = error ? `${selectId}-error` : undefined
  const control = (
    <div className="relative">
      <select
        ref={ref}
        id={selectId}
        aria-invalid={error ? true : undefined}
        aria-describedby={errorId}
        className={`h-10 w-full appearance-none rounded-control border bg-surface pl-3 pr-9 text-sm text-ink shadow-xs outline-none transition duration-150 ease-out-soft focus:border-brand focus:ring-2 focus:ring-brand/30 ${
          error ? 'border-danger' : 'border-hairline'
        } ${className}`}
        {...rest}
      >
        {children}
      </select>
      <ChevronDown
        size={16}
        aria-hidden
        className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-muted"
      />
    </div>
  )

  if (!label && !error) return control

  return (
    <div className="flex flex-col gap-1.5">
      {label ? (
        <label htmlFor={selectId} className="text-sm font-medium text-ink">
          {label}
        </label>
      ) : null}
      {control}
      {error ? (
        <p id={errorId} className="text-xs text-danger">
          {error}
        </p>
      ) : null}
    </div>
  )
})
