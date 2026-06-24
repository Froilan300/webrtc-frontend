import asyncio
import logging
import time
from pathlib import Path

import cv2

from .camera_service import CameraService

logger = logging.getLogger(__name__)

MEDIA_DIR = Path(__file__).resolve().parent.parent / "media"
FPS = 20


class MediaService:
    """Captura foto y graba vídeo de la cámara en vivo, guardándolos en /media."""

    def __init__(self, camera: CameraService):
        self.camera = camera
        MEDIA_DIR.mkdir(exist_ok=True)
        self._recording = False
        self._writer: cv2.VideoWriter | None = None
        self._task: asyncio.Task | None = None
        self._size = None
        self._current_file = None

    @property
    def is_recording(self) -> bool:
        return self._recording

    # ── Foto ──────────────────────────────────────────────────────────────────
    def capture_photo(self):
        frame = self.camera.get_last_frame()
        if frame is None:
            logger.warning("Foto: no hay frame de cámara todavía")
            return None
        name = f"foto_{time.strftime('%Y%m%d_%H%M%S')}.jpg"
        cv2.imwrite(str(MEDIA_DIR / name), frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
        logger.info(f"Foto guardada: {name}")
        return name

    # ── Vídeo ─────────────────────────────────────────────────────────────────
    async def start_recording(self):
        if self._recording:
            return self._current_file
        frame = self.camera.get_last_frame()
        if frame is None:
            logger.warning("Vídeo: no hay frame de cámara todavía")
            return None

        h, w = frame.shape[:2]
        self._size = (w, h)
        name = f"video_{time.strftime('%Y%m%d_%H%M%S')}.mp4"
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        self._writer = cv2.VideoWriter(str(MEDIA_DIR / name), fourcc, FPS, (w, h))
        if not self._writer.isOpened():
            logger.error("No se pudo abrir el VideoWriter")
            self._writer = None
            return None

        self._current_file = name
        self._recording = True
        self._task = asyncio.ensure_future(self._loop())
        logger.info(f"Grabación iniciada: {name}")
        return name

    async def _loop(self):
        loop = asyncio.get_event_loop()
        interval = 1.0 / FPS
        start = time.monotonic()
        written = 0
        while self._recording:
            frame = self.camera.get_last_frame()
            if frame is not None and self._writer is not None:
                if (frame.shape[1], frame.shape[0]) != self._size:
                    frame = cv2.resize(frame, self._size)
                # Escribir tantos frames como correspondan al tiempo REAL transcurrido,
                # para que el vídeo dure lo mismo que la grabación → velocidad correcta
                # (si el bucle se retrasa, duplica el frame actual para ponerse al día).
                target = int((time.monotonic() - start) * FPS)
                while written < target:
                    try:
                        await loop.run_in_executor(None, self._writer.write, frame)
                    except Exception as e:
                        logger.error(f"VideoWriter.write: {e}")
                        break
                    written += 1
            await asyncio.sleep(interval)

    async def stop_recording(self):
        if not self._recording:
            return None
        self._recording = False
        if self._task:
            try:
                await self._task
            except Exception:
                pass
            self._task = None
        if self._writer:
            self._writer.release()
            self._writer = None
        logger.info(f"Grabación detenida: {self._current_file}")
        return self._current_file
