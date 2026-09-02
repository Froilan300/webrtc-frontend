/**
 * StatusBar — barra superior de estado.
 * Logo, conexión, batería (con color), modo, posición (X/Y/rumbo) y estado de
 * patrulla. Lee todo de useRobotStore, que se actualiza con la telemetría.
 */
import { useRobotStore } from '../stores/useRobotStore'

const MODE_LABELS = { 0: 'IDLE', 1: 'BALANCEO', 2: 'TROT', 3: 'CRAWL' }

export function StatusBar() {
  const { isConnected, battery, mode, patrolStatus, position } = useRobotStore()

  // Color de la batería según el nivel (verde/amarillo/rojo)
  const battColor =
    battery > 50 ? 'text-green-400' : battery > 20 ? 'text-yellow-400' : 'text-red-400'

  // Color del estado de patrulla (azul=en marcha, amarillo=pausada, gris=parada)
  const patrolColor =
    patrolStatus === 'RUNNING' ? 'text-blue-400' :
    patrolStatus === 'PAUSED'  ? 'text-yellow-400' : 'text-gray-500'

  return (
    <header className="flex items-center justify-between px-4 py-2 bg-gray-900 border-b border-gray-700 text-base font-mono">
      <div className="flex items-center gap-4">
        <img
          src="/logo.png"
          alt="LincEx Robotics"
          className="h-20 w-auto"
          onError={(e) => { e.currentTarget.style.display = 'none' }}
        />
        <div className="flex items-center gap-2">
          <span className={`w-3 h-3 rounded-full ${isConnected ? 'bg-green-400' : 'bg-red-500'}`} />
          <span className={`text-lg font-bold ${isConnected ? 'text-green-400' : 'text-red-400'}`}>
            {isConnected ? 'Conectado' : 'Desconectado'}
          </span>
        </div>
      </div>

      <div className="flex items-center gap-6 text-base">
        <span className={battColor}>BAT {battery.toFixed(0)}%</span>
        <span className="text-purple-300">MODO: {MODE_LABELS[mode] ?? mode}</span>
        <span className="text-gray-400">
          X {position.x.toFixed(2)} · Y {position.y.toFixed(2)} · HDG {(position.heading * 180 / Math.PI).toFixed(1)}°
        </span>
      </div>

      <span className={`text-lg font-bold ${patrolColor}`}>PATRULLA: {patrolStatus}</span>
    </header>
  )
}
