import { useEffect, useRef } from 'react'

/**
 * Ambient molecular graph behind the hero.
 *
 * Nodes drift slowly and bond to near neighbours. Kept very low-contrast:
 * it should register as texture, not as a graphic. Pauses when off-screen
 * and disables entirely under prefers-reduced-motion.
 */
export default function MoleculeField() {
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const ctx = canvas.getContext('2d')

    let raf = 0
    let w = 0
    let h = 0
    let dpr = 1
    let nodes = []
    let running = true

    const LINK_DIST = 132

    const readInk = () => {
      const cs = getComputedStyle(document.documentElement)
      return {
        node: cs.getPropertyValue('--sage').trim() || '#4F8271',
        line: cs.getPropertyValue('--sage').trim() || '#4F8271',
      }
    }
    let ink = readInk()

    const resize = () => {
      const rect = canvas.getBoundingClientRect()
      dpr = Math.min(window.devicePixelRatio || 1, 2)
      w = rect.width
      h = rect.height
      canvas.width = Math.floor(w * dpr)
      canvas.height = Math.floor(h * dpr)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)

      // density scales with area, capped so large screens stay calm
      const count = Math.min(58, Math.max(18, Math.round((w * h) / 17000)))
      nodes = Array.from({ length: count }, () => ({
        x: Math.random() * w,
        y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.13,
        vy: (Math.random() - 0.5) * 0.13,
        r: 1.1 + Math.random() * 1.5,
      }))
    }

    const draw = () => {
      ctx.clearRect(0, 0, w, h)

      // bonds first, so nodes sit on top
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const a = nodes[i]
          const b = nodes[j]
          const dx = a.x - b.x
          const dy = a.y - b.y
          const d = Math.hypot(dx, dy)
          if (d > LINK_DIST) continue
          const alpha = (1 - d / LINK_DIST) * 0.16
          ctx.strokeStyle = ink.line
          ctx.globalAlpha = alpha
          ctx.lineWidth = 0.7
          ctx.beginPath()
          ctx.moveTo(a.x, a.y)
          ctx.lineTo(b.x, b.y)
          ctx.stroke()
        }
      }

      ctx.globalAlpha = 0.3
      ctx.fillStyle = ink.node
      for (const n of nodes) {
        ctx.beginPath()
        ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2)
        ctx.fill()
      }
      ctx.globalAlpha = 1
    }

    const step = () => {
      if (!running) return
      for (const n of nodes) {
        n.x += n.vx
        n.y += n.vy
        if (n.x < -20) n.x = w + 20
        if (n.x > w + 20) n.x = -20
        if (n.y < -20) n.y = h + 20
        if (n.y > h + 20) n.y = -20
      }
      draw()
      raf = requestAnimationFrame(step)
    }

    resize()

    if (reduced) {
      draw() // one static frame, still decorative but motionless
    } else {
      raf = requestAnimationFrame(step)
    }

    const onResize = () => {
      resize()
      if (reduced) draw()
    }
    window.addEventListener('resize', onResize)

    // stop painting when scrolled away
    const io = new IntersectionObserver(([e]) => {
      if (reduced) return
      if (e.isIntersecting && !running) {
        running = true
        raf = requestAnimationFrame(step)
      } else if (!e.isIntersecting && running) {
        running = false
        cancelAnimationFrame(raf)
      }
    })
    io.observe(canvas)

    const themeWatcher = window.matchMedia('(prefers-color-scheme: dark)')
    const onTheme = () => { ink = readInk() }
    themeWatcher.addEventListener?.('change', onTheme)

    return () => {
      running = false
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', onResize)
      themeWatcher.removeEventListener?.('change', onTheme)
      io.disconnect()
    }
  }, [])

  return <canvas ref={canvasRef} className="molecule-field" aria-hidden="true" />
}
