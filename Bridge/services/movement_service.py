import json
import logging
import random
import time

from unitree_webrtc_connect.constants import RTC_TOPIC, SPORT_CMD, DATA_CHANNEL_TYPE
from .sdk_service import SDKService

logger = logging.getLogger(__name__)


class MovementService:
    def __init__(self, sdk: SDKService):
        self.sdk = sdk

    async def _send(self, api_id: int, parameter: dict | None = None):
        """Comandos puntuales (stand up/down, gait): espera confirmación del robot."""
        if not self.sdk.is_connected:
            return
        opts: dict = {"api_id": api_id}
        if parameter:
            opts["parameter"] = parameter
        try:
            await self.sdk.conn.datachannel.pub_sub.publish_request_new(RTC_TOPIC["SPORT_MOD"], opts)
        except Exception as e:
            logger.error(f"MovementService._send error: {e}")

    def _send_now(self, api_id: int, parameter: dict | None = None):
        """
        Comandos de control en tiempo real (move/stop): FIRE-AND-FORGET.
        No espera el ACK del robot, así nunca se retrasan ni se acumulan aunque
        el LiDAR esté saturando el canal. Lleva priority=1 para adelantarse.
        """
        if not self.sdk.is_connected:
            return
        gen_id = int(time.time() * 1000) % 2147483648 + random.randint(0, 1000)
        payload = {
            "header": {
                "identity": {"id": gen_id, "api_id": api_id},
                "policy": {"priority": 1},
            },
            "parameter": json.dumps(parameter) if parameter is not None else "",
        }
        try:
            self.sdk.conn.datachannel.pub_sub.publish_without_callback(
                RTC_TOPIC["SPORT_MOD"], payload, DATA_CHANNEL_TYPE["REQUEST"]
            )
        except Exception as e:
            logger.error(f"MovementService._send_now error: {e}")

    async def move(self, x: float, y: float, z: float):
        self.sdk.last_move_t = time.monotonic()   # marca "conduciendo" → el LiDAR baja el ritmo
        self._send_now(SPORT_CMD["Move"], {"x": x, "y": y, "z": z})

    async def stop(self):
        # StopMove: corta la velocidad al instante (al soltar tecla = frenada limpia).
        # El robot se queda de pie y quieto, no se desploma.
        self._send_now(SPORT_CMD["StopMove"])

    async def emergency_stop(self):
        # BalanceStand: para en seco y se queda DE PIE y quieto (como frenar un coche),
        # en vez de Damp que lo deja sin fuerza y se desploma.
        self._send_now(SPORT_CMD["BalanceStand"])

    async def stand_up(self):
        await self._send(SPORT_CMD["StandUp"])

    async def stand_down(self):
        await self._send(SPORT_CMD["StandDown"])

    async def set_gait(self, gait: str):
        gait_map = {"NORMAL": 0, "TROT": 1, "CRAWL": 2}
        await self._send(SPORT_CMD["SwitchGait"], {"d": gait_map.get(gait.upper(), 0)})
