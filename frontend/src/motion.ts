import type { Transition, Variants } from 'framer-motion'

/**
 * Central motion system. Durations/easings mirror the CSS tokens in tokens.css so
 * CSS- and JS-driven motion feel identical. Motion is used to *explain* state
 * change (entrance, reorder, displacement, commit) — never to decorate — and the
 * app is wrapped in <MotionConfig reducedMotion="user">, so these honour the
 * user's prefers-reduced-motion setting automatically.
 */

export const DUR = { fast: 0.15, base: 0.25, slow: 0.4 } as const

export const EASE_OUT_SOFT: [number, number, number, number] = [0.16, 1, 0.3, 1]

export const SPRING: Transition = { type: 'spring', stiffness: 420, damping: 34, mass: 0.9 }
export const SPRING_SOFT: Transition = { type: 'spring', stiffness: 260, damping: 30 }

export const fade: Variants = {
  initial: { opacity: 0 },
  animate: { opacity: 1, transition: { duration: DUR.base, ease: EASE_OUT_SOFT } },
  exit: { opacity: 0, transition: { duration: DUR.fast, ease: EASE_OUT_SOFT } },
}

export const fadeUp: Variants = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0, transition: { duration: DUR.base, ease: EASE_OUT_SOFT } },
  exit: { opacity: 0, y: 4, transition: { duration: DUR.fast, ease: EASE_OUT_SOFT } },
}

export const scaleIn: Variants = {
  initial: { opacity: 0, y: 6, scale: 0.98 },
  animate: { opacity: 1, y: 0, scale: 1, transition: SPRING_SOFT },
  exit: { opacity: 0, y: 4, scale: 0.98, transition: { duration: DUR.fast, ease: EASE_OUT_SOFT } },
}

/** Parent variant that staggers its children's entrance. Pair with `fadeUp` children. */
export function staggerContainer(stagger = 0.05, delayChildren = 0): Variants {
  return {
    initial: {},
    animate: { transition: { staggerChildren: stagger, delayChildren } },
  }
}
