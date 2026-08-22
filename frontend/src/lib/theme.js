import { useCallback, useEffect, useState } from 'react'

/**
 * Theme preference is tri-state: 'light' | 'dark' | 'system'.
 *
 * The resolved value ('light' | 'dark') is stamped on <html data-theme>,
 * which is the only selector tokens.css reads. The same resolution runs
 * as an inline script in index.html before first paint, so there is no
 * flash of the wrong theme and no second copy of the dark palette
 * hanging off a prefers-color-scheme media query.
 */

const KEY = 'oncolens-theme'
export const ORDER = ['system', 'light', 'dark']

const mq = () =>
  typeof window !== 'undefined' && window.matchMedia
    ? window.matchMedia('(prefers-color-scheme: dark)')
    : null

export function readPref() {
  try {
    const v = localStorage.getItem(KEY)
    return ORDER.includes(v) ? v : 'system'
  } catch {
    return 'system'
  }
}

export function resolve(pref) {
  if (pref === 'light' || pref === 'dark') return pref
  return mq()?.matches ? 'dark' : 'light'
}

function stamp(pref) {
  const root = document.documentElement
  root.dataset.theme = resolve(pref)
  root.dataset.themePref = pref
}

export function useTheme() {
  const [pref, setPrefState] = useState(readPref)

  // keep the DOM in sync with the preference
  useEffect(() => { stamp(pref) }, [pref])

  // while on 'system', follow the OS if the user flips it mid-session
  useEffect(() => {
    if (pref !== 'system') return
    const m = mq()
    if (!m) return
    const onChange = () => stamp('system')
    m.addEventListener('change', onChange)
    return () => m.removeEventListener('change', onChange)
  }, [pref])

  const setPref = useCallback((next) => {
    try { localStorage.setItem(KEY, next) } catch { /* private mode — session only */ }
    setPrefState(next)
  }, [])

  const cycle = useCallback(() => {
    setPref(ORDER[(ORDER.indexOf(readPref()) + 1) % ORDER.length])
  }, [setPref])

  return { pref, resolved: resolve(pref), setPref, cycle }
}

/**
 * The resolved theme ('light' | 'dark') as a reactive value.
 *
 * Canvas painting cannot use CSS variables, so the two canvases re-read
 * their colours when this changes. Watching the attribute rather than the
 * media query is the point: the in-app toggle changes the attribute
 * without the OS preference moving at all.
 */
export function useResolvedTheme() {
  const [t, setT] = useState(() =>
    typeof document === 'undefined' ? 'light' : document.documentElement.dataset.theme || 'light'
  )
  useEffect(() => {
    const root = document.documentElement
    const sync = () => setT(root.dataset.theme || 'light')
    sync()
    const mo = new MutationObserver(sync)
    mo.observe(root, { attributes: true, attributeFilter: ['data-theme'] })
    return () => mo.disconnect()
  }, [])
  return t
}
