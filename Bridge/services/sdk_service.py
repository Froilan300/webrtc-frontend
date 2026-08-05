import asyncio
import json
import logging
import math
import os
import time
from typing import Callable, Optional

from unitree_webrtc_connect.webrtc_driver import UnitreeWebRTCConnection, WebRTCConnectionMethod
from unitree_webrtc_connect.constants import RTC_TOPIC

logger = logging.getLogger(__name__)

RECONNECT_INTERVAL = 5.0  # s entre intentos de conexión con el robot (modo espera)
STALE_TIMEOUT      = 5.0  # s sin datos del robot => conexión caída (reconectar)
WATCHDOG_TICK      = 1.0  # s entre chequeos del watchdog mientras está conectado

# Cómo conecta el Bridge con el robot (variable de entorno ROBOT_CONN):
#   "auto"     -> prueba primero el WiFi del robot y, si falla, el cable (por defecto)
#   "LocalAP"  -> solo WiFi del robot (192.168.12.1)
#   "LocalSTA" -> solo cable / LAN, en la IP ROBOT_IP
ROBOT_CONN = os.environ.get("ROBOT_CONN", "auto").strip()
ROBOT_IP   = os.environ.get("ROBOT_IP", "192.168.123.161").strip()


class SDKService:
    def __init__(self):
        self.conn: Optional[UnitreeWebRTCConnection] = None
        self.is_connected = False
        self.position: dict = {"x": 0.0, "y": 0.0, "heading": 0.0}
        self.heading: float = 0.0  # actualizado desde lowstate (IMU real)
        self._broadcast: Optional[Callable] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._last_telemetry_t: float = 0.0
        self._last_battery_t: float = 0.0
        self._last_status_t: float = 0.0     # log de estado cada 30 s
        self.last_move_t: float = 0.0        # último comando de movimiento (para priorizar vídeo)
        self.call_active: bool = False       # llamada en curso (para pausar el LiDAR)
        self._on_connected: Optional[Callable] = None   # hook: se llama al conectar (cámara/audio)
        self._should_run: bool = False                  # el supervisor sigue vivo
        self._supervisor_task: Optional[asyncio.Task] = None
        self._last_emit_connected: Optional[bool] = None  # para emitir CONNECTION solo al cambiar
        self._last_rx_t: float = 0.0                      # último dato recibido del robot (watchdog)

    def set_broadcast(self, fn: Callable):
        self._broadcast = fn

    def set_on_connected(self, fn: Callable):
        """Hook que se ejecuta cada vez que el robot pasa a CONECTADO."""
        self._on_connected = fn

    async def start_supervisor(self):
        """Arranca el bucle de conexión en segundo plano. NO bloquea el arranque:
        el Bridge queda operativo (HTTP/WS arriba) aunque el robot esté apagado."""
        self._loop = asyncio.get_running_loop()
        self._should_run = True
        self._supervisor_task = asyncio.create_task(self._supervisor())

    async def _supervisor(self):
        """Espera / reconexión con el robot.

        - Perro apagado: queda EN ESPERA y reintenta cada RECONNECT_INTERVAL s.
        - Perro conectado: vigila que sigan llegando datos (telemetría). Si el robot
          se apaga o pierde el WiFi a mitad de sesión, la telemetría deja de llegar
          y a los STALE_TIMEOUT s lo damos por caído y reconectamos solos.
        """
        waiting_logged = False
        while self._should_run:
            if not self.is_connected:
                if await self._try_connect_once():
                    waiting_logged = False
                    self._last_rx_t = time.monotonic()   # (re)arranca el watchdog
                    await self._emit_connection_status()
                    if self._on_connected:
                        try:
                            await self._on_connected()
                        except Exception as e:
                            logger.error(f"on_connected error: {e}")
                else:
                    if not waiting_logged:
                        logger.info(
                            f"Bridge EN ESPERA del robot — reintentando cada "
                            f"{int(RECONNECT_INTERVAL)}s (enciende el perro cuando quieras)"
                        )
                        waiting_logged = True
                    await self._emit_connection_status()
                    await asyncio.sleep(RECONNECT_INTERVAL)
                    continue
            else:
                # Conectado: watchdog. ¿Siguen llegando datos del robot?
                if time.monotonic() - self._last_rx_t > STALE_TIMEOUT:
                    logger.warning(
                        f"Sin datos del robot durante >{int(STALE_TIMEOUT)}s — "
                        f"conexión caída, reconectando…"
                    )
                    self.is_connected = False
                    await self._emit_connection_status()
                    await self._teardown_conn()
                    continue   # vuelve arriba y reconecta de inmediato
            await asyncio.sleep(WATCHDOG_TICK)

    def _connection_modes(self):
        """Modos de conexión a probar, en orden. En 'auto': primero WiFi, luego cable."""
        ap  = (WebRTCConnectionMethod.LocalAP,  None,     "LocalAP (WiFi del robot)")
        sta = (WebRTCConnectionMethod.LocalSTA, ROBOT_IP, f"LocalSTA (cable, {ROBOT_IP})")
        m = ROBOT_CONN.lower()
        if m == "localap":
            return [ap]
        if m == "localsta":
            return [sta]
        return [ap, sta]   # auto: si el WiFi falla, prueba el cable

    async def _try_connect_once(self) -> bool:
        """Un intento de conexión. Prueba los modos configurados en orden y
        devuelve True en cuanto uno conecta; False si ninguno lo consigue."""
        for method, ip, label in self._connection_modes():
            try:
                self.conn = (UnitreeWebRTCConnection(method, ip=ip)
                             if ip else UnitreeWebRTCConnection(method))
                task = asyncio.create_task(self.conn.connect())
                try:
                    await asyncio.wait_for(asyncio.shield(task), timeout=15.0)
                    logger.info(f"Robot conectado ({label})")
                except asyncio.TimeoutError:
                    logger.info(f"Robot conectado — data channel OK, video pendiente ({label})")
                self.is_connected = True
                self._subscribe()
                return True
            except (Exception, SystemExit) as e:
                logger.warning(f"No conecta por {label}: {e}")
                await self._teardown_conn()
        self.is_connected = False
        return False

    async def _emit_connection_status(self):
        """Avisa al frontend del estado de conexión, solo cuando cambia."""
        if self._broadcast and self.is_connected != self._last_emit_connected:
            self._last_emit_connected = self.is_connected
            try:
                await self._broadcast({"type": "CONNECTION", "data": {"connected": self.is_connected}})
            except Exception:
                pass

    async def _teardown_conn(self):
        """Cierra la conexión a medio abrir (evita acumular peers en cada reintento)."""
        if self.conn is not None:
            try:
                await self.conn.disconnect()
            except Exception:
                pass
            self.conn = None

    def _subscribe(self):
        self.conn.datachannel.pub_sub.subscribe(RTC_TOPIC["SPORT_MOD_STATE"], self._on_sport_state)
        self.conn.datachannel.pub_sub.subscribe(RTC_TOPIC["LOW_STATE"], self._on_low_state)

    @staticmethod
    def _parse_message(message: dict):
        raw = message.get("data", {})
        try:
            return json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            return None

    def _on_sport_state(self, message: dict):
        state = self._parse_message(message)
        if state is None:
            return
        self._last_rx_t = time.monotonic()   # dato fresco del robot (watchdog)

        pos = state.get("position", [0.0, 0.0, 0.0])
        imu = state.get("imu_state")
        rpy = imu.get("rpy", [0.0, 0.0, 0.0]) if isinstance(imu, dict) else [0.0, 0.0, 0.0]

        self.position = {
            "x": pos[0] if len(pos) > 0 else 0.0,
            "y": pos[1] if len(pos) > 1 else 0.0,
            "heading": rpy[2] if len(rpy) > 2 else 0.0,
        }

        self._emit({
            "type": "TELEMETRY",
            "data": {
                "position": self.position,
                "mode": state.get("mode", 0),
                "gait": state.get("gait", 0),
            },
        })

    def _on_low_state(self, message: dict):
        state = self._parse_message(message)
        if state is None:
            return

        imu = state.get("imu_state")
        if isinstance(imu, dict):
            rpy = imu.get("rpy", [])
            if len(rpy) > 2:
                self.heading = rpy[2]

        now = time.monotonic()
        self._last_rx_t = now   # dato fresco del robot (watchdog)

        # Enviar heading real al canvas a 10 Hz (lowstate llega a ~500 Hz)
        if now - self._last_telemetry_t >= 0.1:
            self._last_telemetry_t = now
            self.position["heading"] = self.heading
            self._emit({"type": "TELEMETRY", "data": {"position": self.position, "mode": 0, "gait": 0}})

        # Batería cada 5 s es suficiente
        if now - self._last_battery_t >= 5.0:
            self._last_battery_t = now
            bms = state.get("bms_state", {}) if isinstance(state, dict) else {}
            self._emit({"type": "BATTERY", "data": {"level": bms.get("soc", 0)}})

        # Log de estado cada 30 s (temperatura motores, batería, heading)
        if now - self._last_status_t >= 30.0:
            self._last_status_t = now
            bms  = state.get("bms_state", {}) if isinstance(state, dict) else {}
            mots = state.get("motor_state", []) if isinstance(state, dict) else []
            temps = [m.get("temperature", 0) for m in mots[:12] if isinstance(m, dict)]
            rpy  = (imu.get("rpy", [0, 0, 0]) if isinstance(imu, dict) else [0, 0, 0])
            logger.info(
                f"[STATUS] Batería={bms.get('soc', '?')}% | "
                f"Voltaje={state.get('power_v', '?'):.1f}V | "
                f"Heading={math.degrees(rpy[2] if len(rpy) > 2 else 0):.1f}° | "
                f"Temp motores={temps}"
            )

    def _emit(self, msg: dict):
        if self._broadcast and self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._broadcast(msg), self._loop)

    def _emit_text(self, text: str):
        """Envía un mensaje ya serializado como JSON string — sin json.dumps en el event loop."""
        if self._broadcast and self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._broadcast(text), self._loop)

    async def disconnect(self):
        self._should_run = False
        if self._supervisor_task:
            self._supervisor_task.cancel()
            try:
                await self._supervisor_task
            except asyncio.CancelledError:
                pass
            self._supervisor_task = None
        await self._teardown_conn()
        self.is_connected = False