# stores — Estado global (Zustand)

Estado compartido entre componentes. Con Zustand, cualquier componente lee un
trozo del estado y **se repinta solo** cuando ese trozo cambia.

| Store | Qué guarda | Quién lo actualiza |
|---|---|---|
| `useRobotStore.js` | Estado del robot | `websocketService` (con la telemetría) |
| `useMapStore.js` | Estado del mapa/rutas | `MapView` y `PatrolPanel` |

## `useRobotStore.js`

| Estado | Significado |
|---|---|
| `isConnected` | Si el robot está conectado |
| `battery` | Nivel de batería (%) |
| `position` | `{ x, y, heading }` — posición y rumbo |
| `mode` | Modo de marcha actual |
| `patrolStatus` | `RUNNING` / `PAUSED` / `STOPPED` |
| `patrolProgress` | Progreso de la patrulla (0–1) |
| `patrolTarget` | Índice del waypoint objetivo actual (-1 = ninguno) |

## `useMapStore.js`

| Estado | Significado |
|---|---|
| `waypoints` | Waypoints que estás colocando (aún sin guardar) |
| `savedRoutes` | Rutas guardadas (cargadas del backend) |
| `activeRoute` | Ruta seleccionada (la que se patrulla o previsualiza) |

## Cómo se usa

```js
// Leer (el componente se repinta cuando cambia):
const battery = useRobotStore(s => s.battery)

// Escribir (normalmente desde websocketService o un handler):
useMapStore.getState().addWaypoint({ ... })
```
