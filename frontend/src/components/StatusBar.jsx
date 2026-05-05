import { useRobotStore } from '../stores/useRobotStore'

const MODE_LABELS = { 0: 'IDLE', 1: 'BALANCEO', 2: 'TROT', 3: 'CRAWL' }

export function StatusBar() {
  const { isConnected, battery, mode, patrolStatus, position } = useRobotStore()

  const battColor =
    battery > 50 ? 'text-green-400' : battery > 20 ? 'text-yellow-400' : 'text-red-400'

  const patrolColor =
    patrolStatus === 'RUNNING' ? 'text-blue-400' :
    patrolStatus === 'PAUSED'  ? 'text-yellow-400' : 'text-gray-500'

  return (
    <header className="flex items-center justify-between px-4 py-2 bg-gray-900 border-b border-gray-700 text-sm font-mono">
      <div className="flex items-center gap-2">
        <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-400' : 'bg-red-500'}`} />
        <span className={isConnected ? 'text-green-400' : 'text-red-400'}>
          {isConnected ? 'Conectado' : 'Desconectado'}
        </span>
      </div>

      <div className="flex items-center gap-6 text-xs">
        <span className={battColor}>BAT {battery.toFixed(0)}%</span>
        <span className="text-purple-300">MODO: {MODE_LABELS[mode] ?? mode}</span>
        <span className="text-gray-400">
          X {position.x.toFixed(2)} · Y {position.y.toFixed(2)} · HDG {(position.heading * 180 / Math.PI).toFixed(1)}°
        </span>
      </div>

      <span className={patrolColor}>PATRULLA: {patrolStatus}</span>
    </header>
  )
}
