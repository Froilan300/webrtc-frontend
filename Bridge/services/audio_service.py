import logging
from unitree_webrtc_connect.constants import RTC_TOPIC
from .sdk_service import SDKService

logger = logging.getLogger(__name__)


class AudioService:
    def __init__(self, sdk: SDKService):
        self.sdk = sdk
        self.is_active = False

    async def start(self):
        if not self.sdk.is_connected:
            return
        try:
            self.sdk.conn.audio.switchAudioChannel(True)
            self.is_active = True
            logger.info("Canal de audio abierto")
        except Exception as e:
            logger.error(f"AudioService.start error: {e}")

    async def stop(self):
        if not self.sdk.is_connected:
            return
        try:
            self.sdk.conn.audio.switchAudioChannel(False)
            self.is_active = False
        except Exception as e:
            logger.error(f"AudioService.stop error: {e}")

    async def set_volume(self, level: int):
        if not self.sdk.is_connected:
            return
        try:
            await self.sdk.conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["VUI"],
                {"api_id": 1006, "parameter": {"volume": max(0, min(100, int(level)))}},
            )
        except Exception as e:
            logger.error(f"AudioService.set_volume error: {e}")
