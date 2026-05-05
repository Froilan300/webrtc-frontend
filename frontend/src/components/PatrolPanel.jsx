import { useEffect, useState } from 'react'
import { useMapStore } from '../stores/useMapStore'
import { useRobotStore } from '../stores/useRobotStore'
import { ws } from '../services/websocketService'

export function PatrolPanel() {
  const { waypoints, savedRoutes, activeRoute, setSavedRoutes, setActiveRoute, clearWaypoints } = useMapStore()
  const { patrolStatus, patrolProgress } = useRobotStore()
  const [name, setName] = useState('')
  const [loop, setLoop] = useState(false)
  const isRunning = patrolStatus === 'RUNNING'
  const isActive  = patrolStatus === 'RUNNING' || patrolStatus === 'PAUSED'

  useEffect(() => {
    fetch('/api/routes')
      .then(r => r.json())
      .then(routes => setSavedRoutes(routes))
      .catch(() => {})
  }, [setSavedRoutes])

  const saveRoute = async () => {
    if (!name.trim() || waypoints.length === 0) return
    const route = { name, waypoints, is_loop: loop }
    try {
      const res  = await fetch('/api/routes', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(route),
      })
      const saved = await res.json()
      setSavedRoutes([...savedRoutes, saved])
      setActiveRoute(saved)
      clearWaypoints()
      setName('')
    } catch {}
  }

  const deleteRoute = async (id) => {
    try {
      await fetch(`/api/routes/${id}`, { method: 'DELETE' })
      setSavedRoutes(savedRoutes.filter(r => r.id !== id))
      if (activeRoute?.id === id) setActiveRoute(null)
    } catch {}
  }

  const startPatrol = () => {
    if (!activeRoute) return
    ws.send('START_PATROL', { route_id: activeRoute.id })
  }

  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        <input
          className="flex-1 bg-gray-700 text-white text-sm rounded px-2 py-1 border border-gray-600 focus:outline-none focus:border-blue-500"
          placeholder="Nombre de ruta..."
          value={name}
          onChange={e => setName(e.target.value)}
        />
        <label className="flex items-center gap-1 text-xs text-gray-400 cursor-pointer shrink-0">
          <input type="checkbox" checked={loop} onChange={e => setLoop(e.target.checked)} className="accent-blue-500" />
          Loop
        </label>
        <button
          className="bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold rounded px-3 py-1 transition-colors shrink-0"
          onClick={saveRoute}
        >
          Guardar
        </button>
      </div>

      <div className="space-y-1 max-h-28 overflow-y-auto">
        {savedRoutes.length === 0 && (
          <p className="text-xs text-gray-600">Sin rutas guardadas. Añade waypoints en el mapa.</p>
        )}
        {savedRoutes.map(r => (
          <div
            key={r.id}
            className={`flex items-center justify-between rounded px-2 py-1 cursor-pointer text-xs transition-colors
              ${activeRoute?.id === r.id ? 'bg-blue-900 border border-blue-600' : 'bg-gray-700 hover:bg-gray-600'}`}
            onClick={() => setActiveRoute(r)}
          >
            <span className="text-gray-200 font-medium">{r.name}</span>
            <span className="text-gray-500">{r.waypoints.length} WP{r.is_loop ? ' · loop' : ''}</span>
            <button
              className="text-red-400 hover:text-red-300 ml-2"
              onClick={e => { e.stopPropagation(); deleteRoute(r.id) }}
            >
              ✕
            </button>
          </div>
        ))}
      </div>

      {isRunning && (
        <div className="w-full bg-gray-700 rounded-full h-1.5">
          <div
            className="bg-blue-500 h-1.5 rounded-full transition-all"
            style={{ width: `${patrolProgress * 100}%` }}
          />
        </div>
      )}

      <div className="flex gap-2">
        {!isActive ? (
          <button
            className="flex-1 bg-green-700 hover:bg-green-600 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-bold rounded py-2 transition-colors"
            onClick={startPatrol}
            disabled={!activeRoute}
          >
            Iniciar patrulla
          </button>
        ) : (
          <button
            className="flex-1 bg-yellow-600 hover:bg-yellow-500 text-white text-sm font-bold rounded py-2 transition-colors"
            onClick={() => ws.send(patrolStatus === 'PAUSED' ? 'RESUME_PATROL' : 'PAUSE_PATROL')}
          >
            {patrolStatus === 'PAUSED' ? 'Reanudar' : 'Pausar'}
          </button>
        )}
        <button
          className="flex-1 bg-red-700 hover:bg-red-600 text-white text-sm font-bold rounded py-2 transition-colors"
          onClick={() => ws.send('STOP_PATROL')}
        >
          Detener
        </button>
      </div>
    </div>
  )
}
