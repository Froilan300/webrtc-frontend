import { create } from 'zustand'

export const useRobotStore = create((set) => ({
  isConnected:    false,
  battery:        0,
  position:       { x: 0, y: 0, heading: 0 },
  mode:           0,
  patrolStatus:   'STOPPED',
  patrolProgress: 0,

  setConnected:    (isConnected) => set({ isConnected }),
  setBattery:      (battery)     => set({ battery }),
  updateTelemetry: (position, mode) => set({ position, mode }),
  setPatrolStatus: (patrolStatus, patrolProgress) => set({ patrolStatus, patrolProgress }),
}))
