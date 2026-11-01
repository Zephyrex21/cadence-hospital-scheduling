import { forwardRef, type TextareaHTMLAttributes } from 'react'

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label: string
  error?: string
  hint?: string
}

/** Labeled multi-line field, styled to match `Input`. */
export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { label, error, hint, id, className = '', ...rest },
  ref,
) {
  const fieldId = id ?? rest.name
  const errorId = error ? `${fieldId}-error` : undefined
  const hintId = hint && !error ? `${fieldId}-hint` : undefined
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={fieldId} className="text-[13px] font-medium text-slate">
        {label}
      </label>
      <textarea
        ref={ref}
        id={fieldId}
        aria-invalid={error ? true : undefined}
        aria-describedby={errorId ?? hintId}
        className={`min-h-[84px] resize-y rounded-control border bg-surface px-3.5 py-2.5 text-sm text-ink shadow-xs outline-none transition duration-200 ease-out-soft placeholder:text-muted/80 hover:border-muted/40 focus:border-brand focus:ring-4 focus:ring-brand/15 ${
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
