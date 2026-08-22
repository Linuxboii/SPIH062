import { useEffect, useRef } from 'react'

/**
 * Reveal-on-scroll. Adds `is-visible` once, then stops observing —
 * elements never re-animate on scroll-back, which reads as fidgety.
 */
export function useReveal(options = {}) {
  const ref = useRef(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return

    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduced || !('IntersectionObserver' in window)) {
      el.classList.add('is-visible')
      return
    }

    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          el.classList.add('is-visible')
          io.disconnect()
        }
      },
      { threshold: 0.12, rootMargin: '0px 0px -8% 0px', ...options }
    )

    io.observe(el)
    return () => io.disconnect()
  }, [])

  return ref
}

/**
 * Same, for a container whose children stagger in.
 * Children get --reveal-delay set from their index.
 */
export function useRevealGroup(step = 70) {
  const ref = useRef(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return

    const kids = Array.from(el.querySelectorAll('[data-reveal]'))
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches

    if (reduced || !('IntersectionObserver' in window)) {
      kids.forEach((k) => k.classList.add('is-visible'))
      return
    }

    kids.forEach((k, i) => k.style.setProperty('--reveal-delay', `${i * step}ms`))

    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          kids.forEach((k) => k.classList.add('is-visible'))
          io.disconnect()
        }
      },
      { threshold: 0.08, rootMargin: '0px 0px -6% 0px' }
    )

    io.observe(el)
    return () => io.disconnect()
  }, [step])

  return ref
}
