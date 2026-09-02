"""
Bridge Unitree Go2 — servidor FastAPI que conecta el navegador con el robot.

Expone tres superficies:
  • WebSocket `/ws`  → comandos en tiempo real (mover, patrullar, llamar…) y
    telemetría por broadcast (posición, batería, patrulla, LiDAR).
  • HTTP `/video`    → stream MJPEG de la cámara.
  • HTTP `/api/...`  → foto/vídeo, estado, mapas y rutas.

Instancia todos los servicios, enruta cada comando entrante a su servicio
(`_handle`) y reparte a todos los clientes WebSocket lo que emiten los servicios
(`broadcast`). Arranca con `python main.py` (Uvicorn en el puerto 8080).
"""
import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse

from services.sdk_service import SDKService
from services.movement_service import MovementService
from services.camera_service import CameraService
from services.audio_service import AudioService
from services.map_service import MapService
from services.patrol_service import PatrolService
from services.lidar_service import LidarService
from services.media_service import MediaService, MEDIA_DIR

class _SDKFilter(logging.Filter):
    """Bloquea los mensajes ruidosos del SDK de Unitree (lowstate 500Hz, heartbeat, RTC)."""
    _BLOCKED = (
        "message sent", "Received message on data channel",
        "Heartbeat", "Network status", "rtt_probe", "lowstate",
        "aiortc", "aioice", "Receiving audio frame",
        "H264Decoder", "failed to decode, skipping",
    )
    def filter(self, record: logging.LogRecord) -> bool:
        """Devuelve False (descarta) si el mensaje contiene una cadena bloqueada."""
        msg = record.getMessage()
        return not any(b in msg for b in self._BLOCKED)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logging.getLogger().handlers[0].addFilter(_SDKFilter())
logger = logging.getLogger(__name__)

for _noisy in ("unitree_webrtc_connect", "aioice", "aiortc", "aiortc.rtp"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

# --- Servicios ---
sdk = SDKService()
movement = MovementService(sdk)
camera = CameraService(sdk)
audio = AudioService(sdk)
maps = MapService()
patrol = PatrolService(movement, sdk)
lidar = LidarService(sdk)
media = MediaService(camera)

# --- Clientes WebSocket conectados ---
ws_clients: set[WebSocket] = set()
_send_lock = asyncio.Lock()   # serializa los envíos: nunca dos send_text a la vez en el mismo WS


async def broadcast(msg):
    """Envía un mensaje a TODOS los clientes WebSocket. Acepta dict (lo serializa
    aquí) o str (ya serializado en otro hilo — LiDAR). El lock evita dos envíos
    simultáneos sobre el mismo socket; los clientes caídos se descartan."""
    text = msg if isinstance(msg, str) else json.dumps(msg)
    async with _send_lock:
        dead = set()
        for ws in ws_clients:
            try:
                await ws.send_text(text)
            except Exception:
                dead.add(ws)
        ws_clients.difference_update(dead)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida del servidor: al arrancar conecta al robot y, si hay conexión,
    enciende cámara y audio; al apagar, desconecta el robot."""
    sdk.set_broadcast(broadcast)
    await sdk.connect()
    if sdk.is_connected:
        await camera.start()
        await audio.setup_live_audio()
    yield
    await sdk.disconnect()


app = FastAPI(title="Unitree Go2 Bridge", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────── WebSocket ───────────────────────────

@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    """Endpoint WebSocket: acepta al cliente, le manda el estado de conexión y
    procesa cada comando entrante hasta que se desconecta."""
    await websocket.accept()
    ws_clients.add(websocket)
    await websocket.send_json({"type": "CONNECTION", "data": {"connected": sdk.is_connected}})

    try:
        while True:
            msg = await websocket.receive_json()
            await _handle(msg)
    except WebSocketDisconnect:
        ws_clients.discard(websocket)


async def _handle(msg: dict):
    """Enruta un comando del cliente `{type, payload}` al servicio correspondiente
    (mover, parar, patrulla, audio, LiDAR…) y emite el estado que haga falta."""
    cmd = msg.get("type")
    payload = msg.get("payload", {})

    if cmd == "MOVE":
        await movement.move(
            float(payload.get("x", 0)),
            float(payload.get("y", 0)),
            float(payload.get("z", 0)),
        )
    elif cmd == "STOP":
        # Si hay una patrulla en curso, pararla también (si no, sus comandos Move
        # pisarían el stop y el robot seguiría andando).
        if patrol.is_patrolling:
            await patrol.stop()
            await broadcast({"type": "PATROL_STATUS", "data": {"status": "STOPPED", "progress": 0}})
        else:
            await movement.stop()
    elif cmd == "EMERGENCY_STOP":
        if patrol.is_patrolling:
            await patrol.stop()
            await broadcast({"type": "PATROL_STATUS", "data": {"status": "STOPPED", "progress": 0}})
        await movement.emergency_stop()
    elif cmd == "STAND_UP":
        await movement.stand_up()
    elif cmd == "STAND_DOWN":
        await movement.stand_down()
    elif cmd == "SET_GAIT":
        await movement.set_gait(payload.get("gait", "NORMAL"))
    elif cmd == "START_PATROL":
        route = maps.get_route(payload.get("route_id", ""))
        if route:
            asyncio.create_task(patrol.start(route))
            await broadcast({"type": "PATROL_STATUS", "data": {"status": "RUNNING", "progress": 0}})
    elif cmd == "PAUSE_PATROL":
        patrol.pause()
        await broadcast({"type": "PATROL_STATUS", "data": {"status": "PAUSED", "progress": patrol.get_progress(), "target": patrol.current_target}})
    elif cmd == "RESUME_PATROL":
        patrol.resume()
        await broadcast({"type": "PATROL_STATUS", "data": {"status": "RUNNING", "progress": patrol.get_progress(), "target": patrol.current_target}})
    elif cmd == "STOP_PATROL":
        await patrol.stop()
        await broadcast({"type": "PATROL_STATUS", "data": {"status": "STOPPED", "progress": 0}})
    elif cmd == "CALL_START":
        await audio.start_call()
    elif cmd == "CALL_STOP":
        await audio.stop_call()
    elif cmd == "SET_VOLUME":
        await audio.set_volume(payload.get("level", 50))
    elif cmd == "LIDAR_START":
        asyncio.create_task(lidar.start())
    elif cmd == "LIDAR_STOP":
        lidar.stop()
    elif cmd == "LIDAR_RESET":
        lidar.reset()


# ─────────────────────────── HTTP ───────────────────────────

@app.get("/video")
async def video_stream():
    """Stream MJPEG de la cámara (lo consume el `<img src="/video">` del navegador)."""
    return StreamingResponse(
        camera.mjpeg_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


# ─────────────────────────── Foto / Vídeo ───────────────────────────

@app.post("/api/photo")
async def take_photo():
    """Captura una foto del directo y devuelve su nombre de archivo."""
    return {"filename": media.capture_photo()}


@app.post("/api/video/start")
async def video_start():
    """Empieza a grabar vídeo del directo."""
    name = await media.start_recording()
    return {"filename": name, "recording": media.is_recording}


@app.post("/api/video/stop")
async def video_stop():
    """Detiene la grabación y devuelve el nombre del vídeo guardado."""
    return {"filename": await media.stop_recording()}


@app.get("/api/media/{name}")
async def get_media(name: str):
    """Descarga una foto o vídeo guardado (protege contra path traversal)."""
    safe = Path(name).name   # evita path traversal
    path = MEDIA_DIR / safe
    if not path.is_file():
        raise HTTPException(status_code=404, detail="archivo no encontrado")
    return FileResponse(str(path), filename=safe)


@app.get("/api/status")
async def get_status():
    """Estado actual: conexión con el robot, si patrulla y su progreso."""
    return {
        "connected": sdk.is_connected,
        "patrolling": patrol.is_patrolling,
        "progress": patrol.get_progress(),
    }


@app.get("/api/maps")
async def get_maps():
    """Lista todos los mapas guardados."""
    return maps.list_maps()


@app.post("/api/maps")
async def create_map(body: dict):
    """Crea un mapa nuevo con el nombre dado."""
    return maps.create(body.get("name", "Mapa"))


@app.delete("/api/maps/{map_id}")
async def delete_map(map_id: str):
    """Borra un mapa por su id."""
    return {"deleted": maps.delete_map(map_id)}


@app.get("/api/routes")
async def get_routes():
    """Lista todas las rutas de patrulla guardadas."""
    return maps.list_routes()


@app.post("/api/routes")
async def save_route(body: dict):
    """Guarda una ruta de patrulla (waypoints + is_loop)."""
    return maps.save_route(body)


@app.delete("/api/routes/{route_id}")
async def delete_route(route_id: str):
    """Borra una ruta por su id."""
    return {"deleted": maps.delete_route(route_id)}




if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=False)
