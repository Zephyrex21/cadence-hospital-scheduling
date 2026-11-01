import { forwardRef, type InputHTMLAttributes } from 'react'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string
  error?: string
  hint?: string
  /** Keep the label for screen readers but hide it visually (compact search boxes). */
  labelHidden?: boolean
}

/** Labeled input with accessible error wiring (aria-invalid + aria-describedby). */
export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, error, hint, labelHidden, id, className = '', ...rest },
  ref,
) {
  const inputId = id ?? rest.name
  const errorId = error ? `${inputId}-error` : undefined
  const hintId = hint && !error ? `${inputId}-hint` : undefined
  return (
    <div className="flex flex-col gap-1.5">
      <label
        htmlFor={inputId}
        className={labelHidden ? 'sr-only' : 'text-[13px] font-medium text-slate'}
      >
        {label}
      </label>
      <input
        ref={ref}
        id={inputId}
        aria-invalid={error ? true : undefined}
        aria-describedby={errorId ?? hintId}
        className={`h-11 rounded-control border bg-surface px-3.5 text-sm text-ink shadow-xs outline-none transition duration-200 ease-out-soft placeholder:text-muted/80 hover:border-muted/40 focus:border-brand focus:ring-4 focus:ring-brand/15 ${
          error ? 'border-danger' : 'border-hairline'
        } ${className}`}
        {...rest}
      />
      {error ? (
        <p id={errorId} className="text-xs text-danger">
          {error}
        </p>
      ) : hint ? (
        <p id={hintId} className="text-xs text-muted">
          {hint}
        </p>
      ) : null}
    </div>
  )
})
