import { useEffect, useRef, useState } from 'react'
import SmilesDrawer from 'smiles-drawer'
import { useResolvedTheme } from '../lib/theme'

/**
 * Small 2D structure for a grid cell.
 *
 * Two differences from MoleculeCanvas, both about drawing 24 of these at
 * once rather than one:
 *
 *  - it does not parse until the card is near the viewport. Parsing SMILES
 *    is the expensive half, and a page of results is mostly below the fold.
 *  - the geometry is tuned down for a ~128px box: thinner bonds, shorter
 *    bond length, smaller labels.
 *
 * Each card builds its own Drawer. Sharing one across the grid looks like an
 * easy saving and is a real bug: SmilesDrawer.parse hands back its tree in a
 * callback, so a page of cards runs its draws concurrently through whatever
 * drawer they share, and they overwrite each other's canvas state — only the
 * first row or two survive.
 */

export default function MoleculeThumb({ smiles, height = 128 }) {
  const canvasRef = useRef(null)
  const [near, setNear] = useState(false)
  const [failed, setFailed] = useState(false)
  const theme = useResolvedTheme()

  useEffect(() => {
    const el = canvasRef.current
    if (!el || near) return
    if (!('IntersectionObserver' in window)) { setNear(true); return }
    const io = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) { setNear(true); io.disconnect() } },
      { rootMargin: '300px 0px' }   // start a screen early so it is drawn on arrival
    )
    io.observe(el)
    return () => io.disconnect()
  }, [near])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!near || !smiles || !canvas) return
    setFailed(false)

    const cs = getComputedStyle(document.documentElement)
    const ink = cs.getPropertyValue('--ink-3').trim() || '#4E5B54'
    const sage = cs.getPropertyValue('--sage').trim() || '#4F8271'
    const palette = {
      C: ink, N: sage, O: sage, F: sage, CL: sage, BR: sage, I: sage,
      P: sage, S: sage, B: sage, SI: sage, H: ink, BACKGROUND: 'transparent',
    }

    const width = canvas.clientWidth || 220
    try {
      SmilesDrawer.parse(
        smiles,
        (tree) => {
          try {
            new SmilesDrawer.Drawer({
              width,
              height,
              bondThickness: 1,
              bondLength: 12,
              atomVisualization: 'default',
              fontSizeLarge: 5,
              fontSizeSmall: 3.5,
              padding: 8,
              themes: { oncolens: palette },
            }).draw(tree, canvas, 'oncolens', false)
          } catch { setFailed(true) }
        },
        () => setFailed(true)
      )
    } catch { setFailed(true) }
  }, [near, smiles, height, theme])

  return (
    <div className="thumb" aria-hidden="true">
      <canvas ref={canvasRef} className="thumb-canvas" style={{ height }} />
      {(failed || !smiles) && <span className="thumb-none">No structure</span>}
    </div>
  )
}
