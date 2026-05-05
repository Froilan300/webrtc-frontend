import { useState } from 'react'
import { ws } from '../services/websocketService'

export function AudioControls() {
  const [talking, setTalking] = useState(false)
  const [volume, setVolume]   = useState(50)

  const startTalk = () => { setTalking(true);  ws.send('AUDIO_START') }
  const stopTalk  = () => { setTalking(false); ws.send('AUDIO_STOP')  }

  const onVolume = (v) => {
    setVolume(v)
    ws.send('SET_VOLUME', { level: v })
  }

  return (
    <div className="space-y-3">
      <button
        className={`w-full py-3 rounded-lg font-bold text-white select-none transition-all
          ${talking
            ? 'bg-red-500 shadow-red-500/30 shadow-lg scale-95'
            : 'bg-gray-700 hover:bg-gray-600'
          }`}
        onPointerDown={startTalk}
        onPointerUp={stopTalk}
        onPointerLeave={stopTalk}
      >
        {talking ? '● Hablando...' : '🎤 Push to Talk'}
      </button>

      <div className="flex items-center gap-3">
        <span className="text-gray-400 text-sm">🔊</span>
        <input
          type="range" min={0} max={100} value={volume}
          onChange={(e) => onVolume(Number(e.target.value))}
          className="flex-1 accent-blue-500"
        />
        <span className="text-gray-400 text-xs w-8">{volume}%</span>
      </div>
    </div>
  )
}
