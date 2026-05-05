import { useEffect } from 'react'
import { ws } from './services/websocketService'
import { StatusBar }     from './components/StatusBar'
import { CameraView }    from './components/CameraView'
import { ControlPad }    from './components/ControlPad'
import { AudioControls } from './components/AudioControls'
import { MapView }       from './components/MapView'
import { PatrolPanel }   from './components/PatrolPanel'

export default function App() {
  useEffect(() => { ws.connect() }, [])

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex flex-col">
      <StatusBar />

      <main className="flex-1 p-3 grid grid-cols-12 gap-3 min-h-0">

        {/* Columna izquierda — Cámara + Controles + Audio */}
        <div className="col-span-5 flex flex-col gap-3">
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

        {/* Columna derecha — Mapa + Patrulla */}
        <div className="col-span-7 flex flex-col gap-3">
          <section className="bg-gray-900 rounded-lg p-3 border border-gray-800 flex-1">
            <h2 className="text-xs font-bold text-gray-500 uppercase tracking-widest mb-3">
              Mapa SLAM
            </h2>
            <MapView />
          </section>

          <section className="bg-gray-900 rounded-lg p-3 border border-gray-800">
            <h2 className="text-xs font-bold text-gray-500 uppercase tracking-widest mb-3">
              Patrulla Autónoma
            </h2>
            <PatrolPanel />
          </section>
        </div>

      </main>
    </div>
  )
}
