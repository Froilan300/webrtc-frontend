import { create } from 'zustand'

export const useMapStore = create((set) => ({
  waypoints:   [],
  savedRoutes: [],
  activeRoute: null,

  addWaypoint:    (wp) => set((s) => ({ waypoints: [...s.waypoints, wp] })),
  removeWaypoint: (id) => set((s) => ({ waypoints: s.waypoints.filter(w => w.id !== id) })),
  clearWaypoints: ()   => set({ waypoints: [] }),
  setSavedRoutes: (savedRoutes) => set({ savedRoutes }),
  setActiveRoute: (activeRoute) => set({ activeRoute }),
}))
