import { create } from 'zustand'

export const useRobotStore = create((set) => ({
  isConnected:    false,
  battery:        0,
  position:       { x: 0, y: 0, heading: 0 },
  mode:           0,
  patrolStatus:   'STOPPED',
  patrolProgress: 0,
  patrolTarget:   -1,   // índice del waypoint que el robot persigue ahora (-1 = ninguno)

  setConnected:    (isConnected) => set({ isConnected }),
  setBattery:      (battery)     => set({ battery }),
  updateTelemetry: (position, mode) => set({ position, mode }),
  setPatrolStatus: (patrolStatus, patrolProgress, patrolTarget = -1) =>
    set({ patrolStatus, patrolProgress, patrolTarget }),
}))
