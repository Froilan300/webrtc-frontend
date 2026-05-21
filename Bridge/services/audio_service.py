import asyncio
import base64
import fractions
import io
import json
import logging
import queue
import wave
from typing import Optional

import numpy as np
import sounddevice as sd
from aiortc import AudioStreamTrack
from av import AudioFrame

from unitree_webrtc_connect.constants import AUDIO_API, DATA_CHANNEL_TYPE, RTC_TOPIC
from .sdk_service import SDKService

logger = logging.getLogger(__name__)

# WebRTC audio (robot → PC speaker)
SAMPLE_RATE = 48000
CHANNELS    = 2
BLOCK_SIZE  = 960     # 20 ms @ 48 kHz

# Data-channel audio (PC mic → robot speaker)
MIC_RATE  = 16000     # Hz
MIC_CH    = 1         # mono
MIC_BLOCK = 1280      # 80 ms @ 16 kHz → ~3.5 kB base64 → always 1 sub-chunk


class _MicTrack(AudioStreamTrack):
    """Pista silenciosa — mantiene el transceiver WebRTC en sendrecv."""

    kind = "audio"

    def __init__(self):
        super().__init__()
        self._pts = 0

    async def recv(self) -> AudioFrame:
        await asyncio.sleep(0.02)
        frame = AudioFrame(format='s16', layout='stereo')
        frame.samples     = BLOCK_SIZE
        frame.sample_rate = SAMPLE_RATE
        frame.pts         = self._pts
        frame.time_base   = fractions.Fraction(1, SAMPLE_RATE)
        self._pts        += BLOCK_SIZE
        frame.planes[0].update(bytes(BLOCK_SIZE * CHANNELS * 2))
        return frame


class _Speaker:
    """Reproduce en los altavoces del PC el audio que llega del robot por WebRTC."""

    def __init__(self):
        self._buf: queue.Queue = queue.Queue(maxsize=50)
        self._stream: Optional[sd.OutputStream] = None

    def start(self):
        try:
            self._stream = sd.OutputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype='int16',
                blocksize=BLOCK_SIZE,
                callback=self._cb,
            )
            self._stream.start()
            logger.info("Altavoz del PC abierto")
        except Exception as e:
            logger.error(f"Error abriendo altavoz: {e}")

    def stop(self):
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        while not self._buf.empty():
            try:
                self._buf.get_nowait()
            except queue.Empty:
                break

    def _cb(self, outdata, frames, *_):
        try:
            data = self._buf.get_nowait()
            n = min(frames, len(data))
            outdata[:n] = data[:n]
            if n < frames:
                outdata[n:] = 0
        except queue.Empty:
            outdata[:] = 0

    def feed(self, data: np.ndarray):
        if not self._buf.full():
            self._buf.put_nowait(data)


class _MegaphoneStreamer:
    """Captura el micrófono del PC y lo envía al altavoz del robot via UPLOAD_MEGAPHONE."""

    RATE  = MIC_RATE
    CH    = MIC_CH
    BLOCK = MIC_BLOCK

    def __init__(self, sdk: SDKService):
        self._sdk    = sdk
        self._stream: Optional[sd.InputStream] = None
        self._task:   Optional[asyncio.Task]   = None
        self._q:      queue.Queue              = queue.Queue(maxsize=50)
        self._active = False
        self._sent   = 0

    async def start(self):
        self._active = True
        self._sent   = 0
        self._stream = sd.InputStream(
            samplerate=self.RATE,
            channels=self.CH,
            dtype='int16',
            blocksize=self.BLOCK,
            callback=self._cb,
        )
        self._stream.start()
        self._task = asyncio.ensure_future(self._loop())
        logger.info("MegaphoneStreamer iniciado (mic PC → robot via data channel, 16 kHz mono)")

    async def stop(self):
        self._active = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info(f"MegaphoneStreamer parado ({self._sent} chunks enviados)")

    def _cb(self, indata, *_):
        if not self._q.full():
            self._q.put_nowait(indata.copy())

    @staticmethod
    def _make_wav(raw: bytes) -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as w:
            w.setnchannels(MIC_CH)
            w.setsampwidth(2)
            w.setframerate(MIC_RATE)
            w.writeframes(raw)
        return buf.getvalue()

    async def _loop(self):
        while self._active:
            try:
                data = self._q.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.01)
                continue

            try:
                b64 = base64.b64encode(self._make_wav(data.tobytes())).decode()
                sub_chunks = [b64[i:i + 4096] for i in range(0, len(b64), 4096)]
                total = len(sub_chunks)

                for idx, chunk in enumerate(sub_chunks, 1):
                    self._sdk.conn.datachannel.pub_sub.publish_without_callback(
                        topic="rt/api/audiohub/request",
                        data={
                            "header": {
                                "identity": {
                                    "id":     self._sent * 100 + idx,
                                    "api_id": AUDIO_API["UPLOAD_MEGAPHONE"],
                                }
                            },
                            "parameter": json.dumps({
                                "current_block_size": len(chunk),
                                "block_content":       chunk,
                                "current_block_index": idx,
                                "total_block_number":  total,
                            }),
                        },
                        msg_type=DATA_CHANNEL_TYPE["REQUEST"],
                    )

                self._sent += 1
                if self._sent <= 3:
                    logger.info(
                        f"Megaphone chunk #{self._sent}: {len(b64)} bytes base64, "
                        f"{total} sub-chunk(s)"
                    )

            except Exception as e:
                logger.error(f"MegaphoneStreamer: {e}", exc_info=True)


class AudioService:
    def __init__(self, sdk: SDKService):
        self.sdk          = sdk
        self.is_active    = False
        self._call_active = False
        self._mic_track:  Optional[_MicTrack]         = None
        self._speaker:    Optional[_Speaker]           = None
        self._mega:       Optional[_MegaphoneStreamer] = None
        self._frame_logged = False

    # ── Configuración inicial (llamar una vez tras conectar) ──────────────

    async def setup_live_audio(self):
        """Inyecta pista silenciosa en transceiver WebRTC y prepara los objetos de audio."""
        if not self.sdk.is_connected:
            return
        self._mic_track = _MicTrack()
        self._speaker   = _Speaker()
        self._mega      = _MegaphoneStreamer(self.sdk)

        for t in self.sdk.conn.pc.getTransceivers():
            if t.kind == 'audio':
                t.sender.replaceTrack(self._mic_track)
                logger.info("Pista silenciosa registrada en transceiver WebRTC")
                return
        logger.warning("No se encontró transceiver de audio")

    # ── Llamada en tiempo real ────────────────────────────────────────────

    async def start_call(self):
        if self._call_active or not self.sdk.is_connected:
            return
        self._call_active = True
        self.is_active    = True
        self._frame_logged = False

        try:
            await self.sdk.conn.datachannel.pub_sub.publish_request_new(
                "rt/api/audiohub/request",
                {"api_id": AUDIO_API["ENTER_MEGAPHONE"], "parameter": json.dumps({})},
            )
            logger.info("ENTER_MEGAPHONE enviado al robot")
        except Exception as e:
            logger.warning(f"ENTER_MEGAPHONE: {e}")

        if self._mega:
            await self._mega.start()

        if self._speaker:
            self._speaker.start()
            self.sdk.conn.audio.track_callbacks.clear()
            self.sdk.conn.audio.add_track_callback(self._on_robot_audio)
            self.sdk.conn.audio.switchAudioChannel(True)

        logger.info("Llamada iniciada — PC mic→robot via data channel · robot mic→PC via WebRTC")

    async def stop_call(self):
        if not self._call_active:
            return
        self._call_active = False
        self.is_active    = False

        if self._mega:
            await self._mega.stop()

        try:
            self.sdk.conn.audio.switchAudioChannel(False)
            self.sdk.conn.audio.track_callbacks.clear()
        except Exception:
            pass

        if self._speaker:
            self._speaker.stop()

        try:
            await self.sdk.conn.datachannel.pub_sub.publish_request_new(
                "rt/api/audiohub/request",
                {"api_id": AUDIO_API["EXIT_MEGAPHONE"], "parameter": json.dumps({})},
            )
        except Exception as e:
            logger.warning(f"EXIT_MEGAPHONE: {e}")

        logger.info("Llamada terminada")

    async def _on_robot_audio(self, frame):
        """Recibe audio del robot (WebRTC) y lo reproduce en los altavoces del PC."""
        if not self._call_active or not self._speaker:
            return
        try:
            if not self._frame_logged:
                self._frame_logged = True
                logger.info(
                    f"Audio robot — fmt={frame.format.name} "
                    f"layout={frame.layout.name} "
                    f"rate={frame.sample_rate} samples={frame.samples}"
                )

            arr = frame.to_ndarray()

            if arr.dtype.kind == 'f':
                arr = (np.clip(arr, -1.0, 1.0) * 32767).astype(np.int16)
            else:
                arr = arr.astype(np.int16)

            n_ch = len(frame.layout.channels) or 1
            if arr.ndim == 2 and arr.shape[0] == n_ch and arr.shape[1] > n_ch:
                data = arr.T
            else:
                data = arr.flatten().reshape(-1, n_ch)

            if data.shape[1] == 1:
                data = np.column_stack([data, data])

            if len(data) < BLOCK_SIZE:
                data = np.pad(data, ((0, BLOCK_SIZE - len(data)), (0, 0)))
            else:
                data = data[:BLOCK_SIZE]

            self._speaker.feed(data.astype(np.int16))

        except Exception as e:
            logger.error(f"Error audio robot→PC: {e}", exc_info=True)

    # ── Volumen ───────────────────────────────────────────────────────────

    async def set_volume(self, level: int):
        if not self.sdk.is_connected:
            return
        try:
            await self.sdk.conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["VUI"],
                {"api_id": 1006, "parameter": {"volume": max(0, min(100, int(level)))}},
            )
        except Exception as e:
            logger.error(f"AudioService.set_volume: {e}")
