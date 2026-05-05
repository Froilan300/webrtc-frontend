import { useRobotStore } from '../stores/useRobotStore'

export function CameraView() {
  const isConnected = useRobotStore(s => s.isConnected)

  return (
    <div className="relative bg-black rounded-lg overflow-hidden" style={{ aspectRatio: '16/9' }}>
      {isConnected ? (
        <img
          src="/video"
          alt="Cámara robot"
          className="w-full h-full object-cover"
        />
      ) : (
        <div className="absolute inset-0 flex items-center justify-center text-gray-600 text-sm font-mono">
          Sin señal — robot desconectado
        </div>
      )}

      <div className={`absolute top-2 left-2 text-xs font-bold px-2 py-0.5 rounded
        ${isConnected ? 'bg-red-500 text-white' : 'bg-gray-700 text-gray-400'}`}>
        {isConnected ? '● LIVE' : '○ OFF'}
      </div>
    </div>
  )
}
