"""
patrol_service — patrulla autónoma por waypoints.

Recorre una ruta (lista de waypoints) de forma determinista. Para cada tramo
(punto → siguiente punto) hace DOS pasos:
  1. Girar en el sitio hasta mirar al punto, en lazo cerrado con el rumbo REAL
     de la IMU (`sdk.heading`), que es fiable (`_turn_to`).
  2. Avanzar la distancia exacta por TIEMPO (tiempo = distancia / velocidad),
     sin depender de que la odometría se actualice en vivo (`_advance`).

Así "la distancia que marca el mapa = la que recorre el robot". Sigue por
dead-reckoning: tras cada tramo se asume que el robot quedó en el waypoint.
Soporta pausa/reanudación sin saltarse puntos y emite el objetivo actual al
frontend para resaltarlo en el mapa. Ver constantes de calibración abajo.
"""
import asyncio
import logging
import math
from typing import Optional

from .movement_service import MovementService
from .sdk_service import SDKService

logger = logging.getLogger(__name__)

# ─── Ajustes de la patrulla ───────────────────────────────────────────────
FWD_SPEED   = 0.7     # m/s al avanzar (igual que SPEED del control manual WASD).
                      # Si el robot se queda CORTO sube este número, si se PASA bájalo
                      # (así calibras "1 metro = 1 metro").
TURN_SPEED  = 1.7     # rad/s máx al girar (igual que TURN del control manual WASD)
TURN_MIN    = 0.30    # rad/s mín (por debajo el robot ni se mueve)
HEADING_TOL = 0.12    # rad (~7°) — precisión de orientación antes de avanzar
TICK        = 0.1     # s por ciclo de control
TURN_MAX_T  = 12.0    # s máx girando por tramo (seguridad)

# Hacia dónde "mira" el robot cuando heading(IMU)=0, en el frame del mapa.
# +π/2 = adelante es +Y ("arriba" en el mapa) → igual que se dibuja el robot.
# Si al patrullar va 90° torcido, prueba 0.0 o -math.pi/2; si va al revés, math.pi.
HEADING_OFFSET = math.pi / 2


class PatrolService:
    """Ejecuta una ruta de waypoints girando y avanzando tramo a tramo."""

    def __init__(self, movement: MovementService, sdk: SDKService):
        """Guarda los servicios de movimiento y SDK; arranca en estado 'parado'."""
        self.movement = movement
        self.sdk = sdk
        self.is_patrolling = False
        self._paused = False
        self._task: Optional[asyncio.Task] = None
        self._route: Optional[dict] = None
        self._wp_index = 0

    def get_progress(self) -> float:
        """Progreso de la patrulla (0.0–1.0) = waypoints completados / total."""
        if not self._route:
            return 0.0
        wps = self._route.get("waypoints", [])
        return self._wp_index / len(wps) if wps else 0.0

    @property
    def current_target(self) -> int:
        """Índice del waypoint que persigue ahora (-1 si no está patrullando)."""
        return self._wp_index if self.is_patrolling else -1

    async def start(self, route: dict):
        """Inicia la patrulla de una ruta (para la anterior si la había) lanzando
        el bucle `_run` en una tarea aparte."""
        if self.is_patrolling:
            await self.stop()
        self._route = route
        self._wp_index = 0
        self.is_patrolling = True
        self._paused = False
        self._task = asyncio.create_task(self._run())

    def pause(self):
        """Pausa la patrulla (el robot se para; NO se salta waypoints al reanudar)."""
        self._paused = True

    def resume(self):
        """Reanuda la patrulla desde donde se pausó."""
        self._paused = False

    async def stop(self):
        """Detiene la patrulla, cancela la tarea del bucle y para el robot."""
        self.is_patrolling = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self.movement.stop()

    async def _run(self):
        """Bucle principal: recorre los waypoints en orden (repite si es 'loop'),
        avisando del objetivo actual y navegando cada tramo. Al terminar (o al ser
        cancelado) para el robot y avisa al frontend."""
        wps = self._route.get("waypoints", [])
        is_loop = self._route.get("is_loop", False)

        # Punto de partida = donde está el robot ahora (referencia del mapa).
        # A partir de aquí seguimos por "dead reckoning": tras cada tramo el robot
        # queda (aprox.) en el waypoint, así que el siguiente tramo sale de ahí.
        # NO depende de que la odometría se actualice en vivo.
        cx = self.sdk.position.get("x", 0.0)
        cy = self.sdk.position.get("y", 0.0)

        try:
            while self.is_patrolling:
                if self._wp_index >= len(wps):
                    if is_loop:
                        self._wp_index = 0
                    else:
                        break

                target = wps[self._wp_index]["position"]
                # Avisar del objetivo actual → el mapa lo resalta y la barra avanza
                self.sdk._emit({
                    "type": "PATROL_STATUS",
                    "data": {
                        "status": "RUNNING",
                        "progress": self.get_progress(),
                        "target": self._wp_index,
                    },
                })

                await self._go_segment(cx, cy, target["x"], target["y"])

                # Ya estamos (aprox.) en el waypoint → nuevo punto de partida
                cx, cy = target["x"], target["y"]
                self._wp_index += 1
        except asyncio.CancelledError:
            pass
        finally:
            await self.movement.stop()
            self.is_patrolling = False
            self.sdk._emit({
                "type": "PATROL_STATUS",
                "data": {"status": "STOPPED", "progress": 0, "target": -1},
            })

    async def _go_segment(self, x0: float, y0: float, x1: float, y1: float):
        """Un tramo = girar para mirar al punto + avanzar la distancia exacta."""
        dx, dy = x1 - x0, y1 - y0
        dist = math.hypot(dx, dy)
        if dist < 0.03:
            return

        world_angle = math.atan2(dy, dx)          # dirección del tramo (frame mapa)
        target_heading = world_angle - HEADING_OFFSET
        logger.info(
            f"[PATROL] Tramo → girar a heading={math.degrees(target_heading):.0f}° "
            f"y avanzar {dist:.2f}m"
        )

        await self._turn_to(target_heading)       # 1) orientarse
        if not self.is_patrolling:
            return
        await asyncio.sleep(0.2)                   # asentar antes de arrancar
        await self._advance(dist)                  # 2) avanzar la distancia pedida

    async def _turn_to(self, target_heading: float):
        """Gira en el sitio hasta orientar la IMU al ángulo pedido (lazo cerrado).
        Usa una velocidad proporcional al error, con mínimo para vencer inercia y
        un tope de tiempo por seguridad. La pausa no consume tiempo."""
        elapsed = 0.0
        while self.is_patrolling and elapsed < TURN_MAX_T:
            if self._paused:
                await self.movement.stop()
                await asyncio.sleep(0.2)
                continue

            err = math.atan2(
                math.sin(target_heading - self.sdk.heading),
                math.cos(target_heading - self.sdk.heading),
            )
            if abs(err) < HEADING_TOL:
                await self.movement.stop()
                logger.info(f"[PATROL] Orientado (err={math.degrees(err):.0f}°)")
                return

            vz = max(-TURN_SPEED, min(TURN_SPEED, 2.0 * err))
            if abs(vz) < TURN_MIN:                 # vencer inercia
                vz = TURN_MIN if err > 0 else -TURN_MIN
            await self.movement.move(0.0, 0.0, vz)
            elapsed += TICK
            await asyncio.sleep(TICK)

        await self.movement.stop()

    async def _advance(self, dist: float):
        """Avanza recto la distancia pedida por TIEMPO (tiempo = distancia / velocidad).
        No depende de la odometría: si dices 1 m, avanza ~1 m. La pausa no consume
        distancia (reanuda donde iba)."""
        total_ticks = max(1, round((dist / FWD_SPEED) / TICK))
        logger.info(f"[PATROL] Avanzando {dist:.2f}m (~{total_ticks * TICK:.1f}s)")
        done = 0
        while self.is_patrolling and done < total_ticks:
            if self._paused:
                await self.movement.stop()
                await asyncio.sleep(0.2)
                continue    # la pausa NO consume distancia
            await self.movement.move(FWD_SPEED, 0.0, 0.0)
            done += 1
            await asyncio.sleep(TICK)
        await self.movement.stop()
        logger.info("[PATROL] Tramo completado")
