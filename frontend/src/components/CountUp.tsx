import { animate, useMotionValue, useMotionValueEvent } from 'framer-motion'
import { useEffect, useState } from 'react'

import { EASE_OUT_SOFT } from '../motion'

/** Animated integer count-up. Honours prefers-reduced-motion (jumps to the value). */
export function CountUp({ value, className }: { value: number; className?: string }) {
  const mv = useMotionValue(0)
  const [display, setDisplay] = useState(0)

  useMotionValueEvent(mv, 'change', (v) => setDisplay(Math.round(v)))

  useEffect(() => {
    const reduce =
      typeof window !== 'undefined' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduce) {
      mv.set(value)
      setDisplay(value)
      return
    }
    const controls = animate(mv, value, { duration: 0.7, ease: EASE_OUT_SOFT })
    return () => controls.stop()
  }, [value, mv])

  return (
    <span className={className}>
      <span aria-hidden="true">{display}</span>
      {/* The animating digits are decorative; expose the real value to AT. */}
      <span className="sr-only">{value}</span>
    </span>
  )
}
