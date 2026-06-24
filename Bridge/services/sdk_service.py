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
    def __init__(self):
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
        self._broadcast = fn

    async def connect(self):
        self._loop = asyncio.get_running_loop()
        try:
            self.conn = UnitreeWebRTCConnection(WebRTCConnectionMethod.LocalAP)
            task = asyncio.create_task(self.conn.connect())
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=15.0)
                logger.info("Robot conectado (LocalAP)")
            except asyncio.TimeoutError:
                logger.info("Robot conectado — data channel OK (video pendiente)")
            self.is_connected = True
            self._subscribe()
        except (Exception, SystemExit) as e:
            logger.warning(f"Robot no disponible: {e}")
            self.is_connected = False

    def _subscribe(self):
        self.conn.datachannel.pub_sub.subscribe(RTC_TOPIC["SPORT_MOD_STATE"], self._on_sport_state)
        self.conn.datachannel.pub_sub.subscribe(RTC_TOPIC["LOW_STATE"], self._on_low_state)

    @staticmethod
    def _parse_message(message: dict):
        raw = message.get("data", {})
        try:
            return json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            return None

    def _on_sport_state(self, message: dict):
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
        if self._broadcast and self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._broadcast(msg), self._loop)

    def _emit_text(self, text: str):
        """Envía un mensaje ya serializado como JSON string — sin json.dumps en el event loop."""
        if self._broadcast and self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._broadcast(text), self._loop)

    async def disconnect(self):
        if self.conn is not None:
            try:
                await self.conn.disconnect()
            except Exception:
                pass
        self.is_connected = False
