import { useEffect, useRef, useState } from 'react'
import { useRobotStore } from '../stores/useRobotStore'
import { useMapStore } from '../stores/useMapStore'

const SCALE = 70   // px por metro (tamaño de cada cuadro de la cuadrícula)

export function MapView() {
  const wrapRef   = useRef(null)
  const canvasRef = useRef(null)
  const [size, setSize] = useState({ w: 420, h: 215 })
  const { position } = useRobotStore()
  const patrolTarget = useRobotStore(s => s.patrolTarget)
  const patrolStatus = useRobotStore(s => s.patrolStatus)
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

    // El robot SIEMPRE va en el centro; el mundo se desplaza a su alrededor,
    // así nunca se sale de la pantalla en una patrulla larga.
    const cx = position.x, cy = position.y
    const toCanvas = (wx, wy) => ({
      px: W / 2 + (wx - cx) * SCALE,
      py: H / 2 - (wy - cy) * SCALE,
    })

    ctx.fillStyle = '#111827'
    ctx.fillRect(0, 0, W, H)

    // Cuadrícula que se desplaza con el robot (da sensación de avance)
    ctx.strokeStyle = '#1e293b'
    ctx.lineWidth = 1
    const offX = ((((W / 2 - cx * SCALE) % SCALE) + SCALE) % SCALE)
    for (let x = offX; x <= W; x += SCALE) {
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke()
    }
    const offY = ((((H / 2 + cy * SCALE) % SCALE) + SCALE) % SCALE)
    for (let y = offY; y <= H; y += SCALE) {
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke()
    }

    // Ruta activa (la que se está patrullando): línea + puntos numerados
    if (activeRoute && activeRoute.waypoints.length) {
      const pts = activeRoute.waypoints
      const patrolling = patrolStatus === 'RUNNING' || patrolStatus === 'PAUSED'

      if (pts.length > 1) {
        ctx.strokeStyle = '#6366f1'
        ctx.lineWidth   = 2
        ctx.setLineDash([5, 5])
        ctx.beginPath()
        pts.forEach((wp, i) => {
          const { px, py } = toCanvas(wp.position.x, wp.position.y)
          i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py)
        })
        if (activeRoute.is_loop) {
          const { px, py } = toCanvas(pts[0].position.x, pts[0].position.y)
          ctx.lineTo(px, py)
        }
        ctx.stroke()
        ctx.setLineDash([])
      }

      pts.forEach((wp, i) => {
        const { px, py } = toCanvas(wp.position.x, wp.position.y)
        const isTarget = patrolling && i === patrolTarget
        ctx.fillStyle = isTarget ? '#22c55e' : '#6366f1'
        ctx.beginPath(); ctx.arc(px, py, isTarget ? 11 : 7, 0, Math.PI * 2); ctx.fill()
        if (isTarget) {   // anillo pulsante alrededor del objetivo actual
          ctx.strokeStyle = '#22c55e'; ctx.lineWidth = 2
          ctx.beginPath(); ctx.arc(px, py, 18, 0, Math.PI * 2); ctx.stroke()
        }
        ctx.fillStyle = '#fff'
        ctx.font = 'bold 12px monospace'
        ctx.fillText(`${i + 1}`, px - 3, py - 13)
      })
    }

    // Waypoints en edición (los que estás colocando antes de guardar la ruta)
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

    // Robot: siempre en el centro del canvas
    ctx.save()
    ctx.translate(W / 2, H / 2)
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
  }, [position, waypoints, activeRoute, patrolTarget, patrolStatus, size])

  const handleClick = (e) => {
    const rect = canvasRef.current.getBoundingClientRect()
    const { w: W, h: H } = size
    const px = (e.clientX - rect.left) * (W / rect.width)
    const py = (e.clientY - rect.top)  * (H / rect.height)
    // El click es relativo a la posición ACTUAL del robot (que está en el centro)
    const wx = position.x + (px - W / 2) / SCALE
    const wy = position.y - (py - H / 2) / SCALE

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
      <p className="text-xs text-gray-500 shrink-0">
        Click para añadir waypoints · Azul = robot (siempre centrado) · Verde = objetivo actual
      </p>
    </div>
  )
}
