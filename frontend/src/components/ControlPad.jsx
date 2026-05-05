import { useCallback, useEffect, useRef, useState } from 'react'
import { ws } from '../services/websocketService'

const SPEED = 0.5
const TURN  = 0.5
const ZERO  = { x: 0, y: 0, z: 0 }

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
      const v = { x: 0, y: 0, z: 0 }
      if (pressed.has('ArrowUp')    || pressed.has('w')) v.x =  SPEED
      if (pressed.has('ArrowDown')  || pressed.has('s')) v.x = -SPEED
      if (pressed.has('ArrowLeft')  || pressed.has('a')) v.z =  TURN
      if (pressed.has('ArrowRight') || pressed.has('d')) v.z = -TURN
      if (pressed.has('q')) v.y =  SPEED
      if (pressed.has('e')) v.y = -SPEED
      setVec(v)
    }

    const kd = (e) => { pressed.add(e.key); update() }
    const ku = (e) => { pressed.delete(e.key); update() }
    window.addEventListener('keydown', kd)
    window.addEventListener('keyup',   ku)
    return () => {
      window.removeEventListener('keydown', kd)
      window.removeEventListener('keyup',   ku)
    }
  }, [])

  useEffect(() => {
    if (!mountedRef.current) { mountedRef.current = true; return }
    sendVec(vec)
    if (intervalRef.current) clearInterval(intervalRef.current)
    if (vec.x !== 0 || vec.y !== 0 || vec.z !== 0) {
      intervalRef.current = setInterval(() => sendVec(vec), 100)
    }
    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
  }, [vec, sendVec])

  const down = (v) => setVec(v)
  const up   = ()  => setVec(ZERO)

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

      <p className="text-xs text-gray-500 text-center">WASD / Flechas · Q/E lateral</p>
    </div>
  )
}
