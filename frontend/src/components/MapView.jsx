import { useEffect, useRef } from 'react'
import { useRobotStore } from '../stores/useRobotStore'
import { useMapStore } from '../stores/useMapStore'

const W     = 420
const H     = 215
const SCALE = 20

function toCanvas(wx, wy) {
  return { px: W / 2 + wx * SCALE, py: H / 2 - wy * SCALE }
}

export function MapView() {
  const canvasRef = useRef(null)
  const { position } = useRobotStore()
  const { waypoints, activeRoute } = useMapStore()

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')

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
      ctx.beginPath(); ctx.arc(px, py, 6, 0, Math.PI * 2); ctx.fill()
      ctx.fillStyle = '#fff'
      ctx.font      = '10px monospace'
      ctx.fillText(`${wp.label || `WP${idx + 1}`} (${dist.toFixed(1)}m)`, px + 8, py + 4)
    })

    const { px: rx, py: ry } = toCanvas(position.x, position.y)
    ctx.save()
    ctx.translate(rx, ry)
    ctx.rotate(-position.heading)
    ctx.fillStyle   = '#3b82f6'
    ctx.strokeStyle = '#93c5fd'
    ctx.lineWidth   = 1.5
    ctx.beginPath()
    ctx.moveTo(0, -10)
    ctx.lineTo(-7, 8)
    ctx.lineTo(7, 8)
    ctx.closePath()
    ctx.fill()
    ctx.stroke()
    ctx.restore()
  }, [position, waypoints, activeRoute])

  const handleClick = (e) => {
    const rect   = canvasRef.current.getBoundingClientRect()
    const scaleX = W / rect.width
    const scaleY = H / rect.height
    const px = (e.clientX - rect.left) * scaleX
    const py = (e.clientY - rect.top)  * scaleY
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
    <div className="space-y-1">
      <canvas
        ref={canvasRef}
        width={W}
        height={H}
        onClick={handleClick}
        className="rounded-lg border border-gray-700 cursor-crosshair w-full"
      />
      <p className="text-xs text-gray-500">Click para añadir waypoints · Azul = robot</p>
    </div>
  )
}
