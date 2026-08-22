import { useCallback, useEffect, useState } from 'react'

/**
 * Theme is a binary switch that starts out following the OS.
 *
 * Stored preference is 'light' | 'dark' once the user has chosen, and
 * 'system' until then — but 'system' is a starting condition, never a
 * position on the control. An earlier version cycled system → light →
 * dark, which meant that on a machine set to dark, "system" and "dark"
 * rendered exactly the same page: one press in three did nothing
 * visible, and two of the three icons were indistinguishable. A toggle
 * whose states cannot be told apart is not a toggle.
 *
 * So: no stored choice → follow the OS, live. First press → an explicit
 * light or dark that sticks and stops tracking the OS.
 *
 * The resolved value ('light' | 'dark') is stamped on <html data-theme>,
 * which is the only selector tokens.css reads. The same resolution runs
 * as an inline script in index.html before first paint, so there is no
 * flash of the wrong theme and no second copy of the dark palette
 * hanging off a prefers-color-scheme media query.
 */

const KEY = 'oncolens-theme'
const STORED = ['light', 'dark']

const mq = () =>
  typeof window !== 'undefined' && window.matchMedia
    ? window.matchMedia('(prefers-color-scheme: dark)')
    : null

export function readPref() {
  try {
    const v = localStorage.getItem(KEY)
    return STORED.includes(v) ? v : 'system'
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

  /* flip against what is on screen, not against the stored value —
     from 'system' the user means "give me the other one" */
  const toggle = useCallback(() => {
    setPref(resolve(readPref()) === 'dark' ? 'light' : 'dark')
  }, [setPref])

  return { pref, resolved: resolve(pref), setPref, toggle }
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
