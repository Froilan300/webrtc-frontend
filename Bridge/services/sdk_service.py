import asyncio
import json
import logging
from typing import Callable, Optional

from unitree_webrtc_connect.webrtc_driver import UnitreeWebRTCConnection, WebRTCConnectionMethod
from unitree_webrtc_connect.constants import RTC_TOPIC

logger = logging.getLogger(__name__)


class SDKService:
    def __init__(self):
        self.conn: Optional[UnitreeWebRTCConnection] = None
        self.is_connected = False
        self.position: dict = {"x": 0.0, "y": 0.0, "heading": 0.0}
        self._broadcast: Optional[Callable] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

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

        bms = state.get("bms_state", {}) if isinstance(state, dict) else {}
        self._emit({"type": "BATTERY", "data": {"level": bms.get("soc", 0)}})

    def _emit(self, msg: dict):
        if self._broadcast and self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._broadcast(msg), self._loop)

    async def disconnect(self):
        if self.conn is not None:
            try:
                await self.conn.disconnect()
            except Exception:
                pass
        self.is_connected = False
