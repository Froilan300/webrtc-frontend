import asyncio
import logging
import math
from typing import Optional

from .movement_service import MovementService
from .sdk_service import SDKService

logger = logging.getLogger(__name__)

TOLERANCE = 0.3   # metros — distancia para considerar waypoint alcanzado
SPEED = 0.4       # m/s
MAX_TURN = 0.8    # rad/s


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
                if self._paused:
                    await self.movement.stop()
                    await asyncio.sleep(0.5)
                    continue
                reached = await self._go_to(wps[self._wp_index]["position"])
                if reached:
                    self._wp_index += 1
        except asyncio.CancelledError:
            pass
        finally:
            await self.movement.stop()
            self.is_patrolling = False

    async def _go_to(self, target: dict) -> bool:
        for _ in range(300):  # máx 30 s por waypoint
            if not self.is_patrolling or self._paused:
                return False

            pos = self.sdk.position
            dx = target["x"] - pos["x"]
            dy = target["y"] - pos["y"]
            dist = math.sqrt(dx ** 2 + dy ** 2)

            if dist < TOLERANCE:
                return True

            world_angle = math.atan2(dy, dx)
            rel = math.atan2(
                math.sin(world_angle - pos["heading"]),
                math.cos(world_angle - pos["heading"]),
            )

            vx = SPEED * math.cos(rel)
            vy = SPEED * math.sin(rel)
            vz = max(-MAX_TURN, min(MAX_TURN, rel))

            await self.movement.move(vx, vy, vz)
            await asyncio.sleep(0.1)

        return False
