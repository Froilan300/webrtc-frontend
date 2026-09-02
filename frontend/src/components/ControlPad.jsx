/**
 * ControlPad — control manual del robot.
 * Teclado WASD/flechas (Q/E lateral, Shift = turbo) y D-pad en pantalla; envía
 * comandos MOVE/STOP por WebSocket. Al soltar la tecla o perder el foco para el
 * robot (frenada limpia). Incluye Stand Up/Down y parada de emergencia.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { ws } from '../services/websocketService'

const SPEED = 0.7   // velocidad adelante/atrás (más bajo = no se pasa de largo)
const TURN  = 1.7   // velocidad de giro (más alto = gira más rápido)
const BOOST = 1.5   // multiplicador de velocidad al mantener Shift (turbo)
const ZERO  = { x: 0, y: 0, z: 0 }

// Botón del D-pad: manda su vector al pulsar y para al soltar o salir con el ratón
function DPadBtn({ label, vec, onDown, onUp }) {
  return (
    <button
      className="select-none bg-gray-700 hover:bg-blue-700 active:bg-blue-800 text-white font-bold rounded p-3 transition-colors cursor-pointer"
      onPointerDown={() => onDown(vec)}
      onPointerUp={onUp}
      onPointerLeave={onUp}
    >
      {label}
    </button>
  )
}

export function ControlPad() {
  const [vec, setVec] = useState(ZERO)
  const intervalRef   = useRef(null)
  const mountedRef    = useRef(false)

  // Envía el vector de velocidad: si es cero → STOP, si no → MOVE
  const sendVec = useCallback((v) => {
    if (v.x === 0 && v.y === 0 && v.z === 0) {
      ws.send('STOP')
    } else {
      ws.send('MOVE', v)
    }
  }, [])

  useEffect(() => {
    const pressed = new Set()

    const update = () => {
      const k = pressed.has('shift') ? BOOST : 1   // turbo con Shift
      const v = { x: 0, y: 0, z: 0 }
      if (pressed.has('arrowup')    || pressed.has('w')) v.x =  SPEED * k
      if (pressed.has('arrowdown')  || pressed.has('s')) v.x = -SPEED * k
      if (pressed.has('arrowleft')  || pressed.has('a')) v.z =  TURN
      if (pressed.has('arrowright') || pressed.has('d')) v.z = -TURN
      if (pressed.has('q')) v.y =  SPEED * k
      if (pressed.has('e')) v.y = -SPEED * k
      setVec(v)
    }

    // Normalizamos a minúsculas: así soltar la tecla SIEMPRE la borra del set
    // (si no, con Shift/Mayús el keyup llega en otra caja y el robot no para).
    const kd = (e) => { pressed.add(e.key.toLowerCase()); update() }
    const ku = (e) => { pressed.delete(e.key.toLowerCase()); update() }
    const clear = () => { pressed.clear(); update() }   // al perder el foco, soltar todo
    window.addEventListener('keydown', kd)
    window.addEventListener('keyup',   ku)
    window.addEventListener('blur',    clear)
    return () => {
      window.removeEventListener('keydown', kd)
      window.removeEventListener('keyup',   ku)
      window.removeEventListener('blur',    clear)
    }
  }, [])

  // Cuando cambia el vector, lo envía y, si hay movimiento, lo reenvía cada 100 ms
  // (el robot necesita comandos Move continuos para seguir andando).
  useEffect(() => {
    if (!mountedRef.current) { mountedRef.current = true; return }
    sendVec(vec)
    if (intervalRef.current) clearInterval(intervalRef.current)
    if (vec.x !== 0 || vec.y !== 0 || vec.z !== 0) {
      intervalRef.current = setInterval(() => sendVec(vec), 100)
    }
    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
  }, [vec, sendVec])

  const down = (v) => setVec(v)    // pulsar un botón del D-pad → fija su vector
  const up   = ()  => setVec(ZERO) // soltar → vector cero (para)

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-3 gap-2">
        <button
          className="bg-green-700 hover:bg-green-600 text-white text-xs font-bold rounded py-2 transition-colors"
          onClick={() => ws.send('STAND_UP')}
        >
          Stand Up
        </button>
        <button
          className="bg-yellow-700 hover:bg-yellow-600 text-white text-xs font-bold rounded py-2 transition-colors"
          onClick={() => ws.send('STAND_DOWN')}
        >
          Stand Down
        </button>
        <button
          className="bg-red-700 hover:bg-red-600 text-white text-xs font-bold rounded py-2 transition-colors"
          onClick={() => ws.send('EMERGENCY_STOP')}
        >
          ⚠ STOP
        </button>
      </div>

      <div className="grid grid-cols-3 gap-1 w-fit mx-auto">
        <div />
        <DPadBtn label="▲" vec={{ x:  SPEED, y: 0, z: 0 }} onDown={down} onUp={up} />
        <div />
        <DPadBtn label="◄" vec={{ x: 0, y: 0, z:  TURN  }} onDown={down} onUp={up} />
        <button
          className="bg-gray-600 hover:bg-gray-500 text-white font-bold rounded p-3 transition-colors cursor-pointer"
          onClick={() => ws.send('STOP')}
        >
          ■
        </button>
        <DPadBtn label="►" vec={{ x: 0, y: 0, z: -TURN  }} onDown={down} onUp={up} />
        <div />
        <DPadBtn label="▼" vec={{ x: -SPEED, y: 0, z: 0 }} onDown={down} onUp={up} />
        <div />
      </div>

      <p className="text-xs text-gray-500 text-center">WASD / Flechas · Q/E lateral · Shift = turbo</p>
    </div>
  )
}
