# components — Componentes de UI

Cada archivo es un componente React (una pieza de la interfaz). Todos llevan un
comentario de cabecera explicando su papel y comentarios en sus funciones.

| Componente | Qué muestra / hace | Lee del store | Envía al backend |
|---|---|---|---|
| **`StatusBar.jsx`** | Barra superior: logo, conexión, batería, modo, posición, patrulla | `useRobotStore` | — |
| **`CameraView.jsx`** | Vídeo en vivo + botones de foto/vídeo + pantalla completa | `isConnected` | REST `/api/photo`, `/api/video/*` |
| **`ControlPad.jsx`** | Control manual WASD / D-pad, Stand Up/Down, Stop | — | `MOVE`, `STOP`, `STAND_*`, `EMERGENCY_STOP` |
| **`AudioControls.jsx`** | Botón de llamada + volumen | — | `CALL_START/STOP`, `SET_VOLUME` |
| **`MapView.jsx`** | Mapa SLAM 2D (robot centrado, waypoints, objetivo) | `position`, `patrol*` | — (los waypoints van al store) |
| **`PatrolPanel.jsx`** | Guardar/elegir rutas · iniciar/pausar/detener patrulla | `patrolStatus`, mapa | `START/PAUSE/RESUME/STOP_PATROL` + REST `/api/routes` |
| **`PointCloudView.jsx`** | Nube de puntos LiDAR 3D (Three.js) + export `.ply` | — (escucha `LIDAR_DATA`) | vía `App`: `LIDAR_START/STOP` |
| **`BatteryAlert.jsx`** | Aviso emergente de batería baja (10 % / 5 %) | `battery`, `isConnected` | — |

## Convenciones

- **Leer estado:** `useRobotStore(...)` / `useMapStore(...)`.
- **Enviar comandos:** `ws.send('TYPE', payload)` (de `services/websocketService`).
- **Estilos:** clases de Tailwind directamente en el JSX.

## De un vistazo: dónde vive cada función de la app

- Mover el robot → `ControlPad`
- Ver / grabar → `CameraView`
- Poner waypoints → `MapView`
- Lanzar la patrulla → `PatrolPanel`
- Hablar por el robot → `AudioControls`
- Ver el mapa LiDAR → `PointCloudView`
