import type { ReactNode } from 'react'

import { Button } from '../../components/Button'
import { Plus, X } from '../../components/icons'

export const LANGUAGES: Record<string, string> = {
  en: 'English',
  hi: 'Hindi',
  bn: 'Bengali',
  ta: 'Tamil',
  te: 'Telugu',
  mr: 'Marathi',
  gu: 'Gujarati',
  kn: 'Kannada',
  ml: 'Malayalam',
  pa: 'Punjabi',
  ur: 'Urdu',
  or: 'Odia',
  as: 'Assamese',
}

export const languageName = (code: string) => LANGUAGES[code] ?? code

export const INSURANCE_SCHEMES: Record<string, string> = {
  none: 'None',
  ayushman_bharat: 'Ayushman Bharat (PM-JAY)',
  cghs: 'CGHS',
  esi: 'ESI',
  private: 'Private insurance',
}

export function FormSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <fieldset className="flex min-w-0 flex-col gap-3 rounded-control border border-hairline p-4">
      <legend className="px-1 text-xs font-semibold uppercase tracking-wide text-muted">
        {title}
      </legend>
      {children}
    </fieldset>
  )
}

/** A list of editable rows with add / remove. `render` draws one row's inputs. */
export function RowList<T>({
  rows,
  onChange,
  blank,
  addLabel,
  render,
}: {
  rows: T[]
  onChange: (rows: T[]) => void
  blank: T
  addLabel: string
  render: (row: T, index: number, update: (patch: Partial<T>) => void) => ReactNode
}) {
  return (
    <div className="flex flex-col gap-3">
      {rows.map((row, i) => (
        <div
          // Rows have no stable id and are only appended/removed, so the index is the key.
          key={i}
          className="relative grid gap-3 rounded-control bg-canvas/70 p-3 pr-10 sm:grid-cols-3"
        >
          {render(row, i, (patch) =>
            onChange(rows.map((r, j) => (j === i ? { ...r, ...patch } : r))),
          )}
          <button
            type="button"
            aria-label={`Remove row ${i + 1}`}
            onClick={() => onChange(rows.filter((_, j) => j !== i))}
            className="absolute right-2 top-2 rounded-control p-1 text-muted outline-none transition hover:text-danger focus-visible:ring-2 focus-visible:ring-brand/40"
          >
            <X size={16} aria-hidden />
          </button>
        </div>
      ))}
      <div>
        <Button type="button" size="sm" variant="secondary" onClick={() => onChange([...rows, blank])}>
          <Plus size={14} weight="bold" aria-hidden />
          {addLabel}
        </Button>
      </div>
    </div>
  )
}

export function Chip({
  tone = 'brand',
  children,
}: {
  tone?: 'brand' | 'danger' | 'muted'
  children: ReactNode
}) {
  const style = {
    brand: 'bg-brand/10 text-brand',
    danger: 'bg-danger/10 text-danger',
    muted: 'bg-canvas text-slate',
  }[tone]
  return <span className={`rounded-pill px-2.5 py-0.5 text-xs font-medium ${style}`}>{children}</span>
}

/** A labelled block in a read-only profile. */
export function Block({
  title,
  children,
  wide,
}: {
  title: string
  children: ReactNode
  wide?: boolean
}) {
  return (
    <div className={`rounded-control bg-canvas/70 px-3.5 py-3 ${wide ? 'sm:col-span-2' : ''}`}>
      <p className="text-xs text-muted">{title}</p>
      <div className="mt-1 break-words text-sm text-ink">{children}</div>
    </div>
  )
}

export const NotRecorded = () => <span className="text-muted">Not recorded</span>
