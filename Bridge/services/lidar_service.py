import asyncio
import json
import logging
import time

import numpy as np

from .sdk_service import SDKService

logger = logging.getLogger(__name__)

# ── Constantes idénticas al ejemplo oficial (plot_lidar_stream.py) ────────────
ROTATE_X_ANGLE = np.pi / 2  # 90 degrees
ROTATE_Z_ANGLE = np.pi      # 180 degrees
minYValue = 0
maxYValue = 100

EMIT_INTERVAL       = 0.5   # ~2 Hz parado: tiempo real, refresca el mapa fluido
DRIVE_EMIT_INTERVAL = 4.0   # conduciendo: 1 cada 4 s → libera CPU/navegador para el vídeo
DRIVING_WINDOW      = 1.2   # se considera "conduciendo" si hubo move hace < 1.2 s


def rotate_points(points, x_angle, z_angle):
    """Rotate points around the x and z axes by given angles. (copiado del ejemplo)"""
    rotation_matrix_x = np.array([
        [1, 0, 0],
        [0, np.cos(x_angle), -np.sin(x_angle)],
        [0, np.sin(x_angle), np.cos(x_angle)]
    ])

    rotation_matrix_z = np.array([
        [np.cos(z_angle), -np.sin(z_angle), 0],
        [np.sin(z_angle), np.cos(z_angle), 0],
        [0, 0, 1]
    ])

    points = points @ rotation_matrix_x.T
    points = points @ rotation_matrix_z.T
    return points


def _process_and_serialize(positions):
    """
    Muestra el mapa ACTUAL del robot (ya completo y deduplicado por su SLAM),
    reemplazándolo cada frame — exactamente como la app oficial de Unitree.
    Se AUTOCENTRA cada frame (igual que el ejemplo) → el mapa se queda siempre
    centrado y se sigue solo al moverte. Devuelve json | None.
    """
    points = np.array(
        [positions[i:i + 3] for i in range(0, len(positions), 3)],
        dtype=np.float32,
    )
    points = np.unique(points, axis=0)
    points = rotate_points(points, ROTATE_X_ANGLE, ROTATE_Z_ANGLE)
    points = points[(points[:, 1] >= minYValue) & (points[:, 1] <= maxYValue)]
    if len(points) == 0:
        return None

    # Autocentrar cada frame (como el ejemplo / app oficial)
    center = points.mean(axis=0)
    offset_points = points - center

    # Auto-alinear: girar el plano del suelo (ejes X,Z) para que la pared más larga
    # quede paralela al eje X → la sala se ve como RECTÁNGULO y no como rombo,
    # da igual con qué orientación estuviera el robot al empezar a mapear.
    if len(offset_points) >= 3:
        xz = offset_points[:, [0, 2]]
        cov = np.cov(xz.T)
        eigvals, eigvecs = np.linalg.eigh(cov)
        if eigvals[1] > eigvals[0] * 1.15:   # solo si la sala es claramente alargada
            v = eigvecs[:, 1]                 # dirección de la pared más larga
            ang = float(np.arctan2(v[1], v[0]))
            ca, sa = np.cos(ang), np.sin(ang)
            x = offset_points[:, 0].copy()
            z = offset_points[:, 2].copy()
            offset_points[:, 0] =  x * ca + z * sa
            offset_points[:, 2] = -x * sa + z * ca

    scalars = np.linalg.norm(offset_points, axis=1)  # color por distancia (ejemplo)

    return json.dumps({
        "type": "LIDAR_DATA",
        "data": {
            "points":  np.round(offset_points, 2).tolist(),
            "scalars": np.round(scalars, 2).tolist(),
        },
    })


class LidarService:
    def __init__(self, sdk: SDKService):
        self._sdk         = sdk
        self.is_active    = False
        self._last_emit_t = 0.0
        self._last_log_t  = 0.0
        self._raw_count   = 0
        self._emit_count  = 0
        self._busy        = False

    async def start(self):
        if not self._sdk.is_connected:
            logger.warning("LiDAR: robot no conectado")
            return

        self.is_active    = True
        self._last_emit_t = 0.0
        self._last_log_t  = time.monotonic()
        self._raw_count   = 0
        self._emit_count  = 0
        self._busy        = False

        try:
            await self._sdk.conn.datachannel.disableTrafficSaving(True)
            logger.info("LiDAR: disableTrafficSaving OK")
        except Exception as e:
            logger.warning(f"LiDAR disableTrafficSaving: {e}")

        try:
            self._sdk.conn.datachannel.set_decoder(decoder_type='libvoxel')
            logger.info("LiDAR: set_decoder libvoxel OK")
        except Exception as e:
            logger.warning(f"LiDAR set_decoder: {e}")

        self._sdk.conn.datachannel.pub_sub.publish_without_callback("rt/utlidar/switch", "on")
        self._sdk.conn.datachannel.pub_sub.subscribe(
            "rt/utlidar/voxel_map_compressed",
            self._on_lidar,
        )
        logger.info("LiDAR activado (muestra el mapa del robot, limpio como el ejemplo)")

    def reset(self):
        """El mapa se autocentra cada frame, así que no hace falta nada aquí."""
        pass

    def stop(self):
        if not self.is_active:
            return
        self.is_active = False
        if self._sdk.is_connected:
            try:
                self._sdk.conn.datachannel.pub_sub.publish_without_callback(
                    "rt/utlidar/switch", "off"
                )
            except Exception:
                pass
        logger.info(
            f"LiDAR parado — callbacks={self._raw_count} | frames={self._emit_count}"
        )

    def _on_lidar(self, message):
        """Callback síncrono — mínimo trabajo aquí."""
        self._raw_count += 1
        if not self.is_active:
            return

        now = time.monotonic()

        if now - self._last_log_t >= 30.0:
            self._last_log_t = now
            logger.info(
                f"[LIDAR] callbacks={self._raw_count} | frames={self._emit_count}"
            )

        # Durante una llamada, el audio es prioritario: el LiDAR se PAUSA
        # (el mapa se queda congelado en pantalla; se reanuda al colgar).
        if self._sdk.call_active:
            return

        # Mientras conduces, el vídeo es prioritario: el LiDAR refresca mucho más lento
        driving  = (now - self._sdk.last_move_t) < DRIVING_WINDOW
        interval = DRIVE_EMIT_INTERVAL if driving else EMIT_INTERVAL
        if now - self._last_emit_t < interval:
            return
        self._last_emit_t = now

        try:
            data = message.get("data", {})
            if not isinstance(data, dict):
                return

            inner = data.get("data", {})
            if isinstance(inner, dict) and "positions" in inner:
                positions = inner["positions"]
            elif "positions" in data:
                positions = data["positions"]
            else:
                return

            if positions is None or len(positions) < 3:
                return

            loop = self._sdk._loop
            if loop and loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self._process_and_emit(positions),
                    loop,
                )

        except Exception as e:
            logger.error(f"[LIDAR] Error en callback: {e}", exc_info=True)

    async def _process_and_emit(self, positions):
        """Procesa un frame; _busy evita solapamientos."""
        if self._busy:
            return
        self._busy = True
        try:
            loop = asyncio.get_event_loop()
            msg_text = await loop.run_in_executor(
                None, _process_and_serialize, positions
            )
            if msg_text:
                self._emit_count += 1
                self._sdk._emit_text(msg_text)
        except Exception as e:
            logger.error(f"[LIDAR] Error procesando frame: {e}", exc_info=True)
        finally:
            self._busy = False
