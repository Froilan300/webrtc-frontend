/**
 * BatteryAlert — aviso emergente de batería baja.
 * Modal al 10 % (amarillo) y al 5 % (rojo), para sentar/cargar el robot antes de
 * que se quede sin batería y se desplome. Se rearma al recargar por encima del 15 %.
 */
import { useEffect, useRef, useState } from 'react'
import { useRobotStore } from '../stores/useRobotStore'

export function BatteryAlert() {
  const battery     = useRobotStore(s => s.battery)
  const isConnected = useRobotStore(s => s.isConnected)
  const [alert, setAlert] = useState(null)   // null | 10 | 5  → qué aviso mostrar
  const warned = useRef({ 10: false, 5: false })   // evita repetir el mismo aviso

  // Vigila la batería: dispara el aviso al cruzar el 10 % y el 5 %, y rearma los
  // avisos si se recarga por encima del 15 %.
  useEffect(() => {
    if (!isConnected || battery <= 0) return   // 0 = aún sin lectura / desconectado

    // Si se recarga por encima del 15%, rearmamos los avisos para la próxima vez
    if (battery > 15) {
      warned.current = { 10: false, 5: false }
      return
    }

    if (battery <= 5 && !warned.current[5]) {
      warned.current[5]  = true
      warned.current[10] = true
      setAlert(5)
    } else if (battery <= 10 && !warned.current[10]) {
      warned.current[10] = true
      setAlert(10)
    }
  }, [battery, isConnected])

  if (alert === null) return null

  const critical = alert === 5

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className={`max-w-md mx-4 rounded-xl border-2 p-6 text-center shadow-2xl
        ${critical ? 'bg-red-950 border-red-500 animate-pulse' : 'bg-yellow-950 border-yellow-500'}`}>
        <div className="text-6xl mb-3">{critical ? '🪫' : '⚠️'}</div>
        <h2 className={`text-2xl font-bold mb-2 ${critical ? 'text-red-300' : 'text-yellow-300'}`}>
          {critical ? '¡Batería crítica!' : 'Batería baja'}
        </h2>
        <p className="text-xl text-gray-100 mb-1">
          Batería al <b>{battery.toFixed(0)}%</b>
        </p>
        <p className="text-sm text-gray-400 mb-5">
          {critical
            ? 'Pon el robot a cargar o siéntalo (Stand Down) YA, antes de que se quede sin batería y se desplome.'
            : 'Ve buscando dónde cargarlo o siéntalo (Stand Down) antes de que baje más.'}
        </p>
        <button
          onClick={() => setAlert(null)}
          className={`px-6 py-2 rounded-lg font-bold text-white transition-colors
            ${critical ? 'bg-red-600 hover:bg-red-500' : 'bg-yellow-600 hover:bg-yellow-500'}`}
        >
          Entendido
        </button>
      </div>
    </div>
  )
}
