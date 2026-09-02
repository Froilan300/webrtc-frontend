/**
 * useRobotStore — estado global del robot (Zustand).
 * Conexión, batería, posición, modo y estado de patrulla (incluido el waypoint
 * objetivo actual). Lo alimenta websocketService con la telemetría del robot.
 */
import { create } from 'zustand'

export const useRobotStore = create((set) => ({
  isConnected:    false,
  battery:        0,
  position:       { x: 0, y: 0, heading: 0 },
  mode:           0,
  patrolStatus:   'STOPPED',
  patrolProgress: 0,
  patrolTarget:   -1,   // índice del waypoint que el robot persigue ahora (-1 = ninguno)

  setConnected:    (isConnected)    => set({ isConnected }),      // conexión con el robot
  setBattery:      (battery)        => set({ battery }),          // nivel de batería (%)
  updateTelemetry: (position, mode) => set({ position, mode }),   // posición + modo (telemetría)
  // Estado de la patrulla: estado, progreso (0–1) y waypoint objetivo actual
  setPatrolStatus: (patrolStatus, patrolProgress, patrolTarget = -1) =>
    set({ patrolStatus, patrolProgress, patrolTarget }),
}))
