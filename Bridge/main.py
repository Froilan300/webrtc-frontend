import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from services.sdk_service import SDKService
from services.movement_service import MovementService
from services.camera_service import CameraService
from services.audio_service import AudioService
from services.map_service import MapService
from services.patrol_service import PatrolService

class _SDKFilter(logging.Filter):
    """Bloquea los mensajes ruidosos del SDK de Unitree (lowstate 500Hz, heartbeat, RTC)."""
    _BLOCKED = (
        "message sent", "Received message on data channel",
        "Heartbeat", "Network status", "rtt_probe", "lowstate",
        "aiortc", "aioice",
    )
    def filter(self, record: logging.LogRecord) -> bool:
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

# --- Clientes WebSocket conectados ---
ws_clients: set[WebSocket] = set()


async def broadcast(msg: dict):
    dead = set()
    for ws in ws_clients:
        try:
            await ws.send_json(msg)
        except Exception:
            dead.add(ws)
    ws_clients.difference_update(dead)


@asynccontextmanager
async def lifespan(app: FastAPI):
    sdk.set_broadcast(broadcast)
    await sdk.connect()
    if sdk.is_connected:
        await camera.start()
        n = await audio.clear_all_files()
        if n:
            logger.info(f"Limpieza inicial: {n} archivo(s) de audio borrado(s) del robot")
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
    cmd = msg.get("type")
    payload = msg.get("payload", {})

    if cmd == "MOVE":
        await movement.move(
            float(payload.get("x", 0)),
            float(payload.get("y", 0)),
            float(payload.get("z", 0)),
        )
    elif cmd == "STOP":
        await movement.stop()
    elif cmd == "EMERGENCY_STOP":
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
        await broadcast({"type": "PATROL_STATUS", "data": {"status": "PAUSED", "progress": patrol.get_progress()}})
    elif cmd == "RESUME_PATROL":
        patrol.resume()
        await broadcast({"type": "PATROL_STATUS", "data": {"status": "RUNNING", "progress": patrol.get_progress()}})
    elif cmd == "STOP_PATROL":
        await patrol.stop()
        await broadcast({"type": "PATROL_STATUS", "data": {"status": "STOPPED", "progress": 0}})
    elif cmd == "AUDIO_START":
        await audio.start()
    elif cmd == "AUDIO_STOP":
        await audio.stop()
    elif cmd == "SET_VOLUME":
        await audio.set_volume(payload.get("level", 50))


# ─────────────────────────── HTTP ───────────────────────────

@app.get("/video")
async def video_stream():
    return StreamingResponse(
        camera.mjpeg_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/api/status")
async def get_status():
    return {
        "connected": sdk.is_connected,
        "patrolling": patrol.is_patrolling,
        "progress": patrol.get_progress(),
    }


@app.get("/api/maps")
async def get_maps():
    return maps.list_maps()


@app.post("/api/maps")
async def create_map(body: dict):
    return maps.create(body.get("name", "Mapa"))


@app.delete("/api/maps/{map_id}")
async def delete_map(map_id: str):
    return {"deleted": maps.delete_map(map_id)}


@app.get("/api/routes")
async def get_routes():
    return maps.list_routes()


@app.post("/api/routes")
async def save_route(body: dict):
    return maps.save_route(body)


@app.delete("/api/routes/{route_id}")
async def delete_route(route_id: str):
    return {"deleted": maps.delete_route(route_id)}


@app.get("/api/audio/files")
async def list_audio_files():
    return {"files": await audio.list_files()}


@app.delete("/api/audio/files")
async def clear_audio_files():
    n = await audio.clear_all_files()
    return {"deleted": n}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=False)
