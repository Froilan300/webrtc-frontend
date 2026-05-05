import logging
from unitree_webrtc_connect.constants import RTC_TOPIC, SPORT_CMD
from .sdk_service import SDKService

logger = logging.getLogger(__name__)


class MovementService:
    def __init__(self, sdk: SDKService):
        self.sdk = sdk

    async def _send(self, api_id: int, parameter: dict | None = None):
        if not self.sdk.is_connected:
            return
        opts: dict = {"api_id": api_id}
        if parameter:
            opts["parameter"] = parameter
        try:
            await self.sdk.conn.datachannel.pub_sub.publish_request_new(RTC_TOPIC["SPORT_MOD"], opts)
        except Exception as e:
            logger.error(f"MovementService._send error: {e}")

    async def move(self, x: float, y: float, z: float):
        await self._send(SPORT_CMD["Move"], {"x": x, "y": y, "z": z})

    async def stop(self):
        await self._send(SPORT_CMD["StopMove"])

    async def emergency_stop(self):
        await self._send(SPORT_CMD["Damp"])

    async def stand_up(self):
        await self._send(SPORT_CMD["StandUp"])

    async def stand_down(self):
        await self._send(SPORT_CMD["StandDown"])

    async def set_gait(self, gait: str):
        gait_map = {"NORMAL": 0, "TROT": 1, "CRAWL": 2}
        await self._send(SPORT_CMD["SwitchGait"], {"d": gait_map.get(gait.upper(), 0)})
