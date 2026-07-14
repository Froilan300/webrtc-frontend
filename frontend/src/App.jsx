import { useEffect, useState, lazy, Suspense } from 'react'
import { ws } from './services/websocketService'
import { StatusBar }    from './components/StatusBar'
import { CameraView }   from './components/CameraView'
import { ControlPad }   from './components/ControlPad'
import { AudioControls }from './components/AudioControls'
import { MapView }      from './components/MapView'
import { PatrolPanel }  from './components/PatrolPanel'
import { BatteryAlert } from './components/BatteryAlert'

const PointCloudView = lazy(() =>
  import('./components/PointCloudView').then(m => ({ default: m.PointCloudView }))
)

export default function App() {
  const [mapMode, setMapMode] = useState('slam')

  useEffect(() => { ws.connect() }, [])

  const toggleMapMode = () => {
    const next = mapMode === 'slam' ? 'cloud' : 'slam'
    setMapMode(next)
    ws.send(next === 'cloud' ? 'LIDAR_START' : 'LIDAR_STOP')
  }

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex flex-col">
      <StatusBar />

      <main className="flex-1 p-3 grid grid-cols-12 gap-3 min-h-0">

        {/* Columna izquierda — siempre visible */}
        <div className="col-span-6 flex flex-col gap-3">
          <CameraView />

          <section className="bg-gray-900 rounded-lg p-3 border border-gray-800">
            <h2 className="text-xs font-bold text-gray-500 uppercase tracking-widest mb-3">
              Control Manual
            </h2>
            <ControlPad />
          </section>

          <section className="bg-gray-900 rounded-lg p-3 border border-gray-800">
            <h2 className="text-xs font-bold text-gray-500 uppercase tracking-widest mb-3">
              Audio
            </h2>
            <AudioControls />
          </section>
        </div>

        {/* Columna derecha */}
        <div className="col-span-6 flex flex-col gap-3 min-h-0">

          {mapMode === 'cloud' ? (
            /* ── Modo LiDAR: ocupa toda la columna derecha ── */
            <section className="flex-1 min-h-0 bg-gray-900 rounded-lg p-3 border border-gray-800 flex flex-col">
              <div className="flex items-center justify-between mb-3 shrink-0">
                <h2 className="text-xs font-bold text-gray-500 uppercase tracking-widest">
                  Nube de Puntos LiDAR
                </h2>
                <button
                  onClick={toggleMapMode}
                  className="text-xs px-2 py-1 rounded border border-gray-600 text-gray-300 hover:bg-gray-700 transition-colors"
                >
                  Ver SLAM
                </button>
              </div>
              <div className="flex-1 min-h-0">
                <Suspense fallback={
                  <div className="flex items-center justify-center h-full text-xs text-gray-500">
                    Cargando visor 3D...
                  </div>
                }>
                  <PointCloudView />
                </Suspense>
              </div>
            </section>

          ) : (
            /* ── Modo SLAM: Mapa (llena el alto) + Patrulla ── */
            <>
              <section className="flex-1 min-h-0 bg-gray-900 rounded-lg p-3 border border-gray-800 flex flex-col">
                <div className="flex items-center justify-between mb-3 shrink-0">
                  <h2 className="text-xs font-bold text-gray-500 uppercase tracking-widest">
                    Mapa SLAM
                  </h2>
                  <button
                    onClick={toggleMapMode}
                    className="text-xs px-2 py-1 rounded border border-gray-600 text-gray-300 hover:bg-gray-700 transition-colors"
                  >
                    Ver LiDAR
                  </button>
                </div>
                <div className="flex-1 min-h-0">
                  <MapView />
                </div>
              </section>

              <section className="bg-gray-900 rounded-lg p-3 border border-gray-800 shrink-0">
                <h2 className="text-xs font-bold text-gray-500 uppercase tracking-widest mb-3">
                  Patrulla Autónoma
                </h2>
                <PatrolPanel />
              </section>
            </>
          )}

        </div>
      </main>

      <BatteryAlert />
    </div>
  )
}
