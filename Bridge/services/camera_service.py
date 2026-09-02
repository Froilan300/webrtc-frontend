"""
camera_service — vídeo del robot como stream MJPEG.

Recibe la pista de vídeo WebRTC del robot (`_recv`), guarda el último frame y
lo sirve como MJPEG (`mjpeg_stream`) para el endpoint `GET /video`, que el
navegador consume con un simple `<img src="/video">`.

El último frame (`get_last_frame`) también lo usa `media_service` para las
fotos y la grabación de vídeo. Si no hay señal, muestra un frame en negro.
"""
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
    """Recibe el vídeo WebRTC del robot y lo reexpone como stream MJPEG."""

    def __init__(self, sdk: SDKService):
        """Prepara la cola de frames y un frame en negro de reserva ('sin señal')."""
        self.sdk = sdk
        self._queue: Queue = Queue(maxsize=2)
        self.is_streaming = False
        self._track_cb_registered = False
        self._last_frame = None

        blank = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(blank, "Sin señal de camara", (130, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (80, 80, 80), 2)
        self._blank = blank

    async def start(self):
        """Enciende el canal de vídeo del robot y registra el callback que recibe
        los frames (solo una vez)."""
        if not self.sdk.is_connected:
            return
        self.sdk.conn.video.switchVideoChannel(True)
        if not self._track_cb_registered:
            self.sdk.conn.video.add_track_callback(self._recv)
            self._track_cb_registered = True
        self.is_streaming = True
        logger.info("Cámara iniciada")

    async def stop(self):
        """Apaga el canal de vídeo del robot."""
        if self.sdk.is_connected:
            self.sdk.conn.video.switchVideoChannel(False)
        self.is_streaming = False

    def get_last_frame(self):
        """Último frame de la cámara (numpy BGR) para foto/vídeo, o None."""
        return self._last_frame

    async def _recv(self, track: MediaStreamTrack):
        """Bucle que recibe frames de la pista WebRTC, los convierte a BGR y los
        deja en `_last_frame` y en la cola (descartando el viejo si está llena)."""
        logger.info("CameraService._recv iniciado — recibiendo frames")
        while self.is_streaming:
            try:
                frame = await track.recv()
                img = frame.to_ndarray(format="bgr24")
                self._last_frame = img
                if self._queue.full():
                    self._queue.get_nowait()
                self._queue.put_nowait(img)
            except Exception as e:
                logger.error(f"CameraService._recv error: {e}")
                break
        logger.info("CameraService._recv terminado")

    async def mjpeg_stream(self) -> AsyncIterator[bytes]:
        """Generador MJPEG (~30 fps): codifica cada frame a JPEG y lo emite con el
        separador `multipart/x-mixed-replace` que entiende el `<img>` del navegador."""
        while True:
            try:
                img = self._queue.get_nowait()
            except Empty:
                img = self._last_frame if self._last_frame is not None else self._blank
            try:
                success, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if success:
                    yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n"
            except Exception as e:
                logger.error(f"mjpeg_stream encode error: {e}")
            await asyncio.sleep(0.033)
