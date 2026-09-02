/**
 * useMapStore — estado global del mapa (Zustand).
 * Waypoints en edición, rutas guardadas y ruta activa (la que se patrulla o se
 * previsualiza en el mapa).
 */
import { create } from 'zustand'

export const useMapStore = create((set) => ({
  waypoints:   [],
  savedRoutes: [],
  activeRoute: null,

  addWaypoint:    (wp) => set((s) => ({ waypoints: [...s.waypoints, wp] })),                   // añade un waypoint
  removeWaypoint: (id) => set((s) => ({ waypoints: s.waypoints.filter(w => w.id !== id) })),   // quita uno por id
  clearWaypoints: ()   => set({ waypoints: [] }),                                              // vacía los waypoints en edición
  setSavedRoutes: (savedRoutes) => set({ savedRoutes }),                                       // fija la lista de rutas guardadas
  setActiveRoute: (activeRoute) => set({ activeRoute }),                                       // fija la ruta activa (se patrulla/previsualiza)
}))
