# services — Lógica del backend por dominio

Cada archivo es un **servicio con una única responsabilidad**. `main.py` los
instancia una vez y les conecta la función `broadcast` para que puedan enviar
datos al navegador. Todos reciben el `SDKService` (la conexión con el robot).

## Servicios

| Servicio | Responsabilidad | Notas clave |
|---|---|---|
| **`sdk_service.py`** | Conexión WebRTC + telemetría | Única pieza que habla con el robot. Publica `position`, `heading`, batería. |
| **`movement_service.py`** | Comandos de movimiento | `move`/`stop` fire-and-forget; `emergency_stop` deja el robot de pie. |
| **`camera_service.py`** | Vídeo → MJPEG | Recibe la pista WebRTC y la sirve en `/video`. Guarda el último frame. |
| **`audio_service.py`** | Audio bidireccional + volumen | PC→robot (megáfono, data channel) y robot→PC (WebRTC). |
| **`media_service.py`** | Foto y grabación | Guarda `.jpg` y `.mp4` en `../media`. Vídeo sincronizado al tiempo real. |
| **`map_service.py`** | Persistencia | CRUD de mapas y rutas como JSON en `../data`. |
| **`patrol_service.py`** | Patrulla autónoma | Por cada tramo: **girar** (rumbo IMU) + **avanzar la distancia exacta** (por tiempo). |
| **`lidar_service.py`** | Mapa LiDAR 3D | Decodifica el voxel map, lo autocentra/alinea y lo emite como nube de puntos. |

## Dependencias entre servicios

```
sdk_service ── (conexión al robot) ──┐
                                     ├─> movement_service ──> patrol_service
                                     ├─> camera_service   ──> media_service
                                     ├─> audio_service
                                     └─> lidar_service
map_service (independiente: solo disco)
```

- **`sdk_service`** es la base: todos lo usan para acceder al robot.
- **`patrol_service`** usa `movement_service` (para mover) y `sdk_service` (rumbo).
- **`media_service`** usa `camera_service` (para los frames).
- **`map_service`** no depende de nadie (solo lee/escribe JSON).

Cada archivo lleva un **docstring de módulo** al principio explicando su papel, y
un docstring en **cada clase y cada método**. Empieza por ahí para entender el
código.
