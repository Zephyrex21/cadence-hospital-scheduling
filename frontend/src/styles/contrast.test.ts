import { describe, expect, it } from 'vitest'

import css from './tokens.css?raw'

/**
 * WCAG AA guard for the design tokens: every text/background pairing the UI relies
 * on must stay ≥ 4.5:1 (normal text) in BOTH themes. Parses tokens.css directly so
 * a palette tweak that breaks contrast fails CI instead of shipping.
 */
function block(selector: ':root' | '.dark'): Record<string, [number, number, number]> {
  const start = css.indexOf(`${selector} {`)
  const body = css.slice(start, css.indexOf('}', start))
  const out: Record<string, [number, number, number]> = {}
  for (const m of body.matchAll(/--c-([a-z0-9-]+):\s*(\d+)\s+(\d+)\s+(\d+)/g)) {
    out[m[1]] = [Number(m[2]), Number(m[3]), Number(m[4])]
  }
  return out
}

const lin = (v: number) => {
  const s = v / 255
  return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
}
const lum = ([r, g, b]: [number, number, number]) =>
  0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
const ratio = (a: [number, number, number], b: [number, number, number]) => {
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

const light = block(':root')
const dark = { ...light, ...block('.dark') }

const PAIRS: [string, string, string][] = [
  ['ink', 'canvas', 'primary text on app background'],
  ['ink', 'surface', 'primary text on cards'],
  ['slate', 'surface', 'secondary text on cards'],
  ['slate', 'canvas', 'secondary text on app background'],
  ['muted', 'surface', 'tertiary text on cards'],
  ['muted', 'canvas', 'tertiary text on app background'],
  ['brand', 'surface', 'links / active nav on cards'],
  ['brand', 'canvas', 'links on app background'],
  ['on-brand', 'brand-fill', 'label on filled primary buttons'],
  ['success', 'surface', 'success text'],
  ['warning', 'surface', 'warning text'],
  ['danger', 'surface', 'danger text'],
  ['ink', 'elevated', 'text in menus / toasts'],
  ['muted', 'elevated', 'secondary text in menus / toasts'],
]

describe.each([
  ['light (cream)', light],
  ['dark (moon black)', dark],
])('%s theme contrast', (_name, tokens) => {
  it.each(PAIRS)('%s on %s (%s) ≥ 4.5:1', (fg, bg) => {
    expect(ratio(tokens[fg], tokens[bg])).toBeGreaterThanOrEqual(4.5)
  })
})
