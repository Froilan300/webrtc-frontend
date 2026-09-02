# services — Comunicación con el backend

| Archivo | Descripción |
|---|---|
| `websocketService.js` | Cliente WebSocket (singleton `ws`). Único canal de comandos + telemetría en tiempo real con el backend. |

## `websocketService.js`

Expone una instancia única, `ws`, que se usa en toda la app:

| Método | Para qué |
|---|---|
| `ws.connect()` | Abre la conexión (con reconexión automática cada 3 s). Se llama una vez en `App`. |
| `ws.send(type, payload)` | Envía un comando al robot, p. ej. `ws.send('MOVE', {x, y, z})`. |
| `ws.on(handler)` / `ws.off(handler)` | Suscribe/desuscribe un handler a los mensajes entrantes (lo usa `PointCloudView` para el LiDAR). |

### Flujo interno

- **Eventos entrantes** (`_dispatch`): `TELEMETRY`, `BATTERY`, `PATROL_STATUS`,
  `CONNECTION` se vuelcan directamente al `useRobotStore`. El resto se reparte a
  los handlers suscritos con `on()`.
- **Reconexión:** si el socket se cierra, marca `desconectado` y reintenta solo.

> El resto de la comunicación (vídeo MJPEG y llamadas REST de foto/vídeo/rutas) va
> por HTTP normal con `fetch` / `<img>`, no por este servicio.
