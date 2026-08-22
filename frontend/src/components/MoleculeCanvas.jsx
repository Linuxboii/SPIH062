import { useEffect, useRef, useState } from 'react'
import SmilesDrawer from 'smiles-drawer'

/**
 * 2D structure depiction, rendered in the browser from SMILES.
 * No server round-trip and no external asset — the structure is drawn from
 * the same string the database stores.
 */
export default function MoleculeCanvas({ smiles, height = 260 }) {
  const canvasRef = useRef(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    if (!smiles || !canvasRef.current) return
    setFailed(false)

    const cs = getComputedStyle(document.documentElement)
    const ink = cs.getPropertyValue('--ink-2').trim() || '#3D4A44'
    const sage = cs.getPropertyValue('--sage').trim() || '#4F8271'

    // Muted, single-hue theme — a rainbow element palette would fight the page.
    const theme = {
      C: ink, N: sage, O: sage, F: sage, CL: sage, BR: sage, I: sage,
      P: sage, S: sage, B: sage, SI: sage, H: ink, BACKGROUND: 'transparent',
    }

    const drawer = new SmilesDrawer.Drawer({
      width: canvasRef.current.clientWidth || 420,
      height,
      bondThickness: 1.1,
      bondLength: 16,
      atomVisualization: 'default',
      fontSizeLarge: 6,
      fontSizeSmall: 4,
      padding: 18,
      themes: { oncolens: theme },
    })

    try {
      SmilesDrawer.parse(
        smiles,
        (tree) => {
          try {
            drawer.draw(tree, canvasRef.current, 'oncolens', false)
          } catch {
            setFailed(true)
          }
        },
        () => setFailed(true)
      )
    } catch {
      setFailed(true)
    }
  }, [smiles, height])

  if (!smiles) {
    return <div className="mol-empty">No structure on record.</div>
  }

  return (
    <div className="mol-wrap">
      <canvas ref={canvasRef} className="mol-canvas" style={{ height }} />
      {failed && (
        <div className="mol-empty">Structure could not be rendered from this SMILES.</div>
      )}
    </div>
  )
}
