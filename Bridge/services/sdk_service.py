"""
sdk_service — conexión WebRTC con el robot y telemetría.

Es la única pieza que habla directamente con el Go2 (vía `unitree_webrtc_connect`).
Se suscribe a dos topics del robot:
  • SPORT_MOD_STATE → posición (x, y) de la odometría.
  • LOW_STATE       → rumbo real de la IMU (yaw) y batería.

Reemite la telemetría al frontend mediante `_emit` (a ~10 Hz, porque el robot
la manda a ~500 Hz). El resto de servicios usan esta clase como puerta de acceso
al robot (`sdk.conn`) y leen `sdk.position` / `sdk.heading`.
"""
import asyncio
import json
import logging
import math
import time
from typing import Callable, Optional

from unitree_webrtc_connect.webrtc_driver import UnitreeWebRTCConnection, WebRTCConnectionMethod
from unitree_webrtc_connect.constants import RTC_TOPIC

logger = logging.getLogger(__name__)


class SDKService:
    """Envuelve la conexión WebRTC con el robot y publica su telemetría."""

    def __init__(self):
        """Inicializa el estado; NO conecta todavía (eso lo hace `connect`)."""
        self.conn: Optional[UnitreeWebRTCConnection] = None
        self.is_connected = False
        self.position: dict = {"x": 0.0, "y": 0.0, "heading": 0.0}
        self.heading: float = 0.0  # actualizado desde lowstate (IMU real)
        self._broadcast: Optional[Callable] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._last_telemetry_t: float = 0.0
        self._last_battery_t: float = 0.0
        self._last_status_t: float = 0.0     # log de estado cada 30 s
        self.last_move_t: float = 0.0        # último comando de movimiento (para priorizar vídeo)
        self.call_active: bool = False       # llamada en curso (para pausar el LiDAR)

    def set_broadcast(self, fn: Callable):
        """Registra la función `broadcast` de main.py que reparte a los WebSocket."""
        self._broadcast = fn

    async def connect(self):
        """Conecta al robot por WebRTC (LocalAP). Si conecta, se suscribe a los
        topics de telemetría. Guarda el event loop para reemitir desde los
        callbacks (que corren en otro hilo)."""
        self._loop = asyncio.get_running_loop()
        try:
            self.conn = UnitreeWebRTCConnection(WebRTCConnectionMethod.LocalAP)
            task = asyncio.create_task(self.conn.connect())
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=15.0)
                logger.info("Robot conectado (LocalAP)")
            except asyncio.TimeoutError:
                # El vídeo puede tardar; el data channel suele estar listo antes.
                logger.info("Robot conectado — data channel OK (video pendiente)")
            self.is_connected = True
            self._subscribe()
        except (Exception, SystemExit) as e:
            logger.warning(f"Robot no disponible: {e}")
            self.is_connected = False

    def _subscribe(self):
        """Se suscribe a SPORT_MOD_STATE (posición) y LOW_STATE (IMU + batería)."""
        self.conn.datachannel.pub_sub.subscribe(RTC_TOPIC["SPORT_MOD_STATE"], self._on_sport_state)
        self.conn.datachannel.pub_sub.subscribe(RTC_TOPIC["LOW_STATE"], self._on_low_state)

    @staticmethod
    def _parse_message(message: dict):
        """Extrae el payload de un mensaje del robot (viene como dict o JSON string)."""
        raw = message.get("data", {})
        try:
            return json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            return None

    def _on_sport_state(self, message: dict):
        """Callback de SPORT_MOD_STATE: guarda la posición (x, y) de la odometría
        y la reemite al frontend como TELEMETRY."""
        state = self._parse_message(message)
        if state is None:
            return

        pos = state.get("position", [0.0, 0.0, 0.0])
        imu = state.get("imu_state")
        rpy = imu.get("rpy", [0.0, 0.0, 0.0]) if isinstance(imu, dict) else [0.0, 0.0, 0.0]

        self.position = {
            "x": pos[0] if len(pos) > 0 else 0.0,
            "y": pos[1] if len(pos) > 1 else 0.0,
            "heading": rpy[2] if len(rpy) > 2 else 0.0,
        }

        self._emit({
            "type": "TELEMETRY",
            "data": {
                "position": self.position,
                "mode": state.get("mode", 0),
                "gait": state.get("gait", 0),
            },
        })

    def _on_low_state(self, message: dict):
        """Callback de LOW_STATE (llega a ~500 Hz): actualiza el rumbo real de la
        IMU y, con límite de frecuencia, reemite rumbo (10 Hz), batería (5 s) y
        un log de estado (30 s)."""
        state = self._parse_message(message)
        if state is None:
            return

        imu = state.get("imu_state")
        if isinstance(imu, dict):
            rpy = imu.get("rpy", [])
            if len(rpy) > 2:
                self.heading = rpy[2]

        now = time.monotonic()

        # Enviar heading real al canvas a 10 Hz (lowstate llega a ~500 Hz)
        if now - self._last_telemetry_t >= 0.1:
            self._last_telemetry_t = now
            self.position["heading"] = self.heading
            self._emit({"type": "TELEMETRY", "data": {"position": self.position, "mode": 0, "gait": 0}})

        # Batería cada 5 s es suficiente
        if now - self._last_battery_t >= 5.0:
            self._last_battery_t = now
            bms = state.get("bms_state", {}) if isinstance(state, dict) else {}
            self._emit({"type": "BATTERY", "data": {"level": bms.get("soc", 0)}})

        # Log de estado cada 30 s (temperatura motores, batería, heading)
        if now - self._last_status_t >= 30.0:
            self._last_status_t = now
            bms  = state.get("bms_state", {}) if isinstance(state, dict) else {}
            mots = state.get("motor_state", []) if isinstance(state, dict) else []
            temps = [m.get("temperature", 0) for m in mots[:12] if isinstance(m, dict)]
            rpy  = (imu.get("rpy", [0, 0, 0]) if isinstance(imu, dict) else [0, 0, 0])
            logger.info(
                f"[STATUS] Batería={bms.get('soc', '?')}% | "
                f"Voltaje={state.get('power_v', '?'):.1f}V | "
                f"Heading={math.degrees(rpy[2] if len(rpy) > 2 else 0):.1f}° | "
                f"Temp motores={temps}"
            )

    def _emit(self, msg: dict):
        """Reparte un dict a los WebSocket desde cualquier hilo (los callbacks del
        SDK no corren en el event loop) usando `run_coroutine_threadsafe`."""
        if self._broadcast and self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._broadcast(msg), self._loop)

    def _emit_text(self, text: str):
        """Como `_emit` pero para un mensaje ya serializado como JSON string
        (lo usa el LiDAR: serializa en un executor y evita json.dumps en el loop)."""
        if self._broadcast and self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._broadcast(text), self._loop)

    async def disconnect(self):
        """Cierra la conexión WebRTC con el robot (al apagar el servidor)."""
        if self.conn is not None:
            try:
                await self.conn.disconnect()
            except Exception:
                pass
        self.is_connected = False
