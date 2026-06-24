import asyncio
import logging
import math
from typing import Optional

from .movement_service import MovementService
from .sdk_service import SDKService

logger = logging.getLogger(__name__)

TOLERANCE = 0.35  # metros — distancia para considerar waypoint alcanzado
SPEED = 0.3       # m/s
MAX_TURN = 0.6    # rad/s
TURN_GAIN = 2.0   # ganancia proporcional del controlador de giro
MAX_TICKS = 600   # máx 60 s de navegación REAL por waypoint (la pausa no cuenta)


class PatrolService:
    def __init__(self, movement: MovementService, sdk: SDKService):
        self.movement = movement
        self.sdk = sdk
        self.is_patrolling = False
        self._paused = False
        self._task: Optional[asyncio.Task] = None
        self._route: Optional[dict] = None
        self._wp_index = 0

    def get_progress(self) -> float:
        if not self._route:
            return 0.0
        wps = self._route.get("waypoints", [])
        return self._wp_index / len(wps) if wps else 0.0

    async def start(self, route: dict):
        if self.is_patrolling:
            await self.stop()
        self._route = route
        self._wp_index = 0
        self.is_patrolling = True
        self._paused = False
        self._task = asyncio.create_task(self._run())

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    async def stop(self):
        self.is_patrolling = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self.movement.stop()

    async def _run(self):
        wps = self._route.get("waypoints", [])
        is_loop = self._route.get("is_loop", False)
        try:
            while self.is_patrolling:
                if self._wp_index >= len(wps):
                    if is_loop:
                        self._wp_index = 0
                    else:
                        break
                await self._go_to(wps[self._wp_index]["position"])
                # Solo se avanza cuando _go_to termina (alcanzado o timeout real);
                # la pausa NO hace que termine, así que ya no se salta waypoints.
                self._wp_index += 1
                # Emitir progreso en vivo → la barra y el mapa avanzan al instante
                self.sdk._emit({
                    "type": "PATROL_STATUS",
                    "data": {"status": "RUNNING", "progress": self.get_progress()},
                })
        except asyncio.CancelledError:
            pass
        finally:
            await self.movement.stop()
            self.is_patrolling = False

    async def _go_to(self, target: dict) -> bool:
        logger.info(f"[PATROL] Navegando a target={target}")
        ticks = 0
        last_log = 0
        while ticks < MAX_TICKS:
            if not self.is_patrolling:
                return False

            # Pausa: paramos y esperamos SIN contar para el timeout ni avanzar
            if self._paused:
                await self.movement.stop()
                await asyncio.sleep(0.2)
                continue

            # Posición REAL del robot (odometría) — la misma que se ve en el mapa
            cx = self.sdk.position.get("x", 0.0)
            cy = self.sdk.position.get("y", 0.0)

            # Go2 IMU: heading=0 → robot apunta +Y (arriba en el canvas).
            # En atan2 la dirección +Y = π/2, por eso el offset +π/2.
            math_heading = self.sdk.heading + math.pi / 2

            dx = target["x"] - cx
            dy = target["y"] - cy
            dist = math.sqrt(dx ** 2 + dy ** 2)

            if dist < TOLERANCE:
                logger.info(f"[PATROL] Waypoint alcanzado en {ticks * 0.1:.1f}s")
                await self.movement.stop()
                return True

            world_angle = math.atan2(dy, dx)
            rel = math.atan2(
                math.sin(world_angle - math_heading),
                math.cos(world_angle - math_heading),
            )

            vz = max(-MAX_TURN, min(MAX_TURN, rel * TURN_GAIN))
            vx = SPEED * max(0.0, math.cos(rel))   # solo avanza si mira al objetivo

            if ticks - last_log >= 20:   # log cada ~2 s
                last_log = ticks
                logger.info(
                    f"[P] t={ticks*0.1:.1f}s | pos=({cx:.2f},{cy:.2f}) | "
                    f"dist={dist:.2f}m rel={math.degrees(rel):.0f}° | vx={vx:.2f} vz={vz:.2f}"
                )

            await self.movement.move(vx, 0.0, vz)
            ticks += 1
            await asyncio.sleep(0.1)

        logger.warning(f"[PATROL] Timeout alcanzando target={target}")
        return False
