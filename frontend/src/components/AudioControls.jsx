/**
 * AudioControls — llamada de audio y volumen.
 * Botón para iniciar/colgar la llamada (tu micro ↔ robot) y slider de volumen.
 * Envía CALL_START / CALL_STOP / SET_VOLUME por WebSocket.
 */
import { useState } from 'react'
import { ws } from '../services/websocketService'

export function AudioControls() {
  const [calling, setCalling] = useState(false)
  const [volume, setVolume]   = useState(50)

  // Inicia o cuelga la llamada de audio con el robot
  const toggleCall = () => {
    if (calling) {
      ws.send('CALL_STOP')
      setCalling(false)
    } else {
      ws.send('CALL_START')
      setCalling(true)
    }
  }

  // Cambia el volumen del robot (0–100) y lo refleja en el slider
  const onVolume = (v) => {
    setVolume(v)
    ws.send('SET_VOLUME', { level: v })
  }

  return (
    <div className="space-y-3">
      <button
        className={`w-full py-3 rounded-lg font-bold text-white transition-all select-none
          ${calling
            ? 'bg-green-600 shadow-green-500/30 shadow-lg animate-pulse'
            : 'bg-gray-700 hover:bg-gray-600'
          }`}
        onClick={toggleCall}
      >
        {calling ? '🔴 En llamada — click para colgar' : '📞 Iniciar llamada'}
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

      {calling && (
        <p className="text-xs text-green-400 text-center">
          Tu voz → altavoz robot · Micrófono robot → tus altavoces
        </p>
      )}
    </div>
  )
}
