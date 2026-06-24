import { useEffect, useRef, useState } from 'react'
import { useRobotStore } from '../stores/useRobotStore'
import { useMapStore } from '../stores/useMapStore'

const SCALE = 70   // tamaño de cada cuadro de la cuadrícula (y zoom del mapa)

export function MapView() {
  const wrapRef   = useRef(null)
  const canvasRef = useRef(null)
  const [size, setSize] = useState({ w: 420, h: 215 })
  const { position } = useRobotStore()
  const { waypoints, activeRoute } = useMapStore()

  // El canvas se ajusta al tamaño real de su contenedor (no escala con el ancho)
  useEffect(() => {
    const wrap = wrapRef.current
    if (!wrap) return
    const ro = new ResizeObserver(() => {
      const w = Math.round(wrap.clientWidth)
      const h = Math.round(wrap.clientHeight)
      if (w > 0 && h > 0) setSize({ w, h })
    })
    ro.observe(wrap)
    return () => ro.disconnect()
  }, [])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const { w: W, h: H } = size
    canvas.width  = W
    canvas.height = H
    const ctx = canvas.getContext('2d')

    const toCanvas = (wx, wy) => ({ px: W / 2 + wx * SCALE, py: H / 2 - wy * SCALE })

    ctx.fillStyle = '#111827'
    ctx.fillRect(0, 0, W, H)

    ctx.strokeStyle = '#1e293b'
    ctx.lineWidth = 1
    for (let i = 0; i <= W; i += SCALE) {
      ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i, H); ctx.stroke()
    }
    for (let i = 0; i <= H; i += SCALE) {
      ctx.beginPath(); ctx.moveTo(0, i); ctx.lineTo(W, i); ctx.stroke()
    }

    if (activeRoute && activeRoute.waypoints.length > 1) {
      ctx.strokeStyle = '#6366f1'
      ctx.lineWidth   = 2
      ctx.setLineDash([5, 5])
      ctx.beginPath()
      activeRoute.waypoints.forEach((wp, i) => {
        const { px, py } = toCanvas(wp.position.x, wp.position.y)
        i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py)
      })
      if (activeRoute.is_loop) {
        const first = activeRoute.waypoints[0]
        const { px, py } = toCanvas(first.position.x, first.position.y)
        ctx.lineTo(px, py)
      }
      ctx.stroke()
      ctx.setLineDash([])
    }

    waypoints.forEach((wp, idx) => {
      const { px, py } = toCanvas(wp.position.x, wp.position.y)
      const prev = idx === 0
        ? { x: position.x, y: position.y }
        : waypoints[idx - 1].position
      const dist = Math.sqrt(
        (wp.position.x - prev.x) ** 2 + (wp.position.y - prev.y) ** 2
      )
      ctx.fillStyle = '#f59e0b'
      ctx.beginPath(); ctx.arc(px, py, 13, 0, Math.PI * 2); ctx.fill()
      ctx.fillStyle = '#fff'
      ctx.font      = '17px monospace'
      ctx.fillText(`${wp.label || `WP${idx + 1}`} (${dist.toFixed(1)}m)`, px + 16, py + 6)
    })

    const { px: rx, py: ry } = toCanvas(position.x, position.y)
    ctx.save()
    ctx.translate(rx, ry)
    ctx.rotate(-position.heading)
    ctx.fillStyle   = '#3b82f6'
    ctx.strokeStyle = '#93c5fd'
    ctx.lineWidth   = 3
    ctx.beginPath()
    ctx.moveTo(0, -30)
    ctx.lineTo(-20, 22)
    ctx.lineTo(20, 22)
    ctx.closePath()
    ctx.fill()
    ctx.stroke()
    ctx.restore()
  }, [position, waypoints, activeRoute, size])

  const handleClick = (e) => {
    const rect = canvasRef.current.getBoundingClientRect()
    const { w: W, h: H } = size
    const px = (e.clientX - rect.left) * (W / rect.width)
    const py = (e.clientY - rect.top)  * (H / rect.height)
    const wx = (px - W / 2) / SCALE
    const wy = -(py - H / 2) / SCALE

    const { waypoints, addWaypoint } = useMapStore.getState()
    addWaypoint({
      id:       crypto.randomUUID(),
      label:    `WP${waypoints.length + 1}`,
      position: { x: wx, y: wy },
    })
  }

  return (
    <div className="flex flex-col h-full gap-1">
      <div ref={wrapRef} className="relative flex-1 min-h-0">
        <canvas
          ref={canvasRef}
          onClick={handleClick}
          className="absolute inset-0 w-full h-full rounded-lg border border-gray-700 cursor-crosshair"
        />
      </div>
      <p className="text-xs text-gray-500 shrink-0">Click para añadir waypoints · Azul = robot</p>
    </div>
  )
}
