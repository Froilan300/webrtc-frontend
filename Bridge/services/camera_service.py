import asyncio
import logging
from queue import Empty, Queue
from typing import AsyncIterator

import cv2
import numpy as np
from aiortc import MediaStreamTrack

from .sdk_service import SDKService

logger = logging.getLogger(__name__)


class CameraService:
    def __init__(self, sdk: SDKService):
        self.sdk = sdk
        self._queue: Queue = Queue(maxsize=2)
        self.is_streaming = False
        self._track_cb_registered = False

        blank = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(blank, "Sin señal de camara", (130, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (80, 80, 80), 2)

        

    async def start(self):
        if not self.sdk.is_connected:
            return
        self.sdk.conn.video.switchVideoChannel(True)
        if not self._track_cb_registered:
            self.sdk.conn.video.add_track_callback(self._recv)
            self._track_cb_registered = True
        self.is_streaming = True
        logger.info("Cámara iniciada")

    async def stop(self):
        if self.sdk.is_connected:
            self.sdk.conn.video.switchVideoChannel(False)
        self.is_streaming = False

    async def _recv(self, track: MediaStreamTrack):
        while self.is_streaming:
            try:
                frame = await track.recv()
                img = frame.to_ndarray(format="bgr24")
                if self._queue.full():
                    self._queue.get_nowait()
                self._queue.put_nowait(img)
            except Exception as e:
                logger.error(f"CameraService._recv error: {e}")
                break

    async def mjpeg_stream(self) -> AsyncIterator[bytes]:
        while True:
            try:
                img = self._queue.get_nowait()
            except Empty:
                img = self._blank
            _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n"
            await asyncio.sleep(0.033)
