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


class PatrolService:
    def __init__(self, movement: MovementService, sdk: SDKService):
        self.movement = movement
        self.sdk = sdk
        self.is_patrolling = False
        self._paused = False
        self._task: Optional[asyncio.Task] = None
        self._route: Optional[dict] = None
        self._wp_index = 0
        self._dr_x: float = 0.0  # posición estimada por dead reckoning
        self._dr_y: float = 0.0

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
        self._dr_x = 0.0
        self._dr_y = 0.0
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
                if self._paused:
                    await self.movement.stop()
                    await asyncio.sleep(0.5)
                    continue
                await self._go_to(wps[self._wp_index]["position"])
                self._wp_index += 1  # always advance — retrying with drifted DR causes false "reached"
        except asyncio.CancelledError:
            pass
        finally:
            await self.movement.stop()
            self.is_patrolling = False

    async def _go_to(self, target: dict) -> bool:
        logger.info(f"[PATROL] Navegando a target={target} desde dr=({self._dr_x:.2f},{self._dr_y:.2f})")
        for tick in range(400):  # máx 40 s por waypoint
            if not self.is_patrolling or self._paused:
                return False

            # Go2 IMU: heading=0 → robot apunta +Y (arriba en canvas).
            # En math atan2: dirección +Y = π/2. Offset = +π/2.
            imu_heading = self.sdk.heading
            math_heading = imu_heading + math.pi / 2

            dx = target["x"] - self._dr_x
            dy = target["y"] - self._dr_y
            dist = math.sqrt(dx ** 2 + dy ** 2)

            if dist < TOLERANCE:
                logger.info(f"[PATROL] Waypoint alcanzado en {tick * 0.1:.1f}s")
                return True

            world_angle = math.atan2(dy, dx)
            rel = math.atan2(
                math.sin(world_angle - math_heading),
                math.cos(world_angle - math_heading),
            )

            vz = max(-MAX_TURN, min(MAX_TURN, rel * TURN_GAIN))
            vx = SPEED * max(0.0, math.cos(rel))

            logger.info(
                f"[P] t={tick*0.1:.1f}s | "
                f"dr=({self._dr_x:.2f},{self._dr_y:.2f}) | "
                f"imu={math.degrees(imu_heading):.1f}° | "
                f"dist={dist:.2f}m rel={math.degrees(rel):.1f}° | "
                f"vx={vx:.2f} vz={vz:.2f}"
            )

            await self.movement.move(vx, 0.0, vz)
            if vx > 0:
                self._dr_x += vx * 0.1 * math.cos(math_heading)
                self._dr_y += vx * 0.1 * math.sin(math_heading)

            await asyncio.sleep(0.1)

        logger.warning(f"[PATROL] Timeout alcanzando target={target}")
        return False
