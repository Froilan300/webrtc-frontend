import asyncio
import base64
import hashlib
import json
import logging
import os
import tempfile
import time
import wave
from typing import Optional

import numpy as np
import sounddevice as sd

from unitree_webrtc_connect.constants import AUDIO_API, RTC_TOPIC
from .sdk_service import SDKService

logger = logging.getLogger(__name__)

SAMPLE_RATE = 44100
CHANNELS    = 1
CHUNK_SIZE  = 4096
CHUNK_SLEEP = 0.05


class AudioService:
    def __init__(self, sdk: SDKService):
        self.sdk = sdk
        self.is_active  = False
        self._frames: list = []
        self._recording    = False
        self._stream: Optional[sd.InputStream] = None

    async def start(self):
        if not self.sdk.is_connected or self._recording:
            return
        self._frames    = []
        self._recording = True
        try:
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype='int16',
                blocksize=1024,
                callback=self._mic_callback,
            )
            self._stream.start()
            self.is_active = True
            logger.info("Captura de micrófono iniciada")
        except Exception as e:
            logger.error(f"AudioService.start error: {e}")
            self._recording = False

    def _mic_callback(self, indata, frames, time_info, status):
        if self._recording:
            self._frames.append(indata.copy())

    async def stop(self):
        if not self._recording:
            return
        self._recording = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        self.is_active = False

        if not self._frames or not self.sdk.is_connected:
            self._frames = []
            return

        file_name = f"ptt_{int(time.time())}"
        tmp_path   = os.path.join(tempfile.gettempdir(), f"{file_name}.wav")

        try:
            audio_data = np.concatenate(self._frames, axis=0)
            self._frames = []
            dur_s = len(audio_data) / SAMPLE_RATE
            logger.info(f"Grabados {dur_s:.1f}s — subiendo al robot")

            with wave.open(tmp_path, 'wb') as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(2)
                wf.setframerate(SAMPLE_RATE)
                wf.writeframes(audio_data.tobytes())

            uuid = await self._upload_wav(tmp_path, file_name)
            if uuid is None:
                logger.warning("No se encontró UUID tras la subida — abortando reproducción")
                return

            # Play once and stop (don't loop through other files on the robot)
            await self.sdk.conn.datachannel.pub_sub.publish_request_new(
                "rt/api/audiohub/request",
                {"api_id": AUDIO_API["SET_PLAY_MODE"], "parameter": json.dumps({"play_mode": "no_cycle"})},
            )

            logger.info(f"Reproduciendo en robot (id={uuid})")
            await self.sdk.conn.datachannel.pub_sub.publish_request_new(
                "rt/api/audiohub/request",
                {
                    "api_id": AUDIO_API["SELECT_START_PLAY"],
                    "parameter": json.dumps({"unique_id": uuid}),
                },
            )
            logger.info("Audio enviado al altavoz del robot")
            asyncio.create_task(self._cleanup_after(uuid, dur_s + 5.0))

        except Exception as e:
            logger.error(f"AudioService.stop error: {e}")
            self._frames = []
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    async def _upload_wav(self, wav_path: str, file_name: str) -> Optional[str]:
        with open(wav_path, 'rb') as f:
            audio_data = f.read()

        file_md5 = hashlib.md5(audio_data).hexdigest()
        b64      = base64.b64encode(audio_data).decode('utf-8')
        chunks   = [b64[i:i + CHUNK_SIZE] for i in range(0, len(b64), CHUNK_SIZE)]
        total    = len(chunks)

        logger.info(f"Subiendo {total} chunks ({len(audio_data)} bytes)")

        for i, chunk in enumerate(chunks, 1):
            await self.sdk.conn.datachannel.pub_sub.publish_request_new(
                "rt/api/audiohub/request",
                {
                    "api_id": AUDIO_API["UPLOAD_AUDIO_FILE"],
                    "parameter": json.dumps({
                        "file_name":            file_name,
                        "file_type":            "wav",
                        "file_size":            len(audio_data),
                        "current_block_index":  i,
                        "total_block_number":   total,
                        "block_content":        chunk,
                        "current_block_size":   len(chunk),
                        "file_md5":             file_md5,
                        "create_time":          int(time.time() * 1000),
                    }, ensure_ascii=True),
                },
            )
            await asyncio.sleep(CHUNK_SLEEP)

        # Retrieve the UUID the robot assigned to the file
        response = await self.sdk.conn.datachannel.pub_sub.publish_request_new(
            "rt/api/audiohub/request",
            {"api_id": AUDIO_API["GET_AUDIO_LIST"], "parameter": json.dumps({})},
        )
        try:
            data_str   = response.get('data', {}).get('data', '{}')
            audio_list = json.loads(data_str).get('audio_list', [])
            audio      = next((a for a in audio_list if a.get('CUSTOM_NAME') == file_name), None)
            return audio.get('UNIQUE_ID') if audio else None
        except Exception as e:
            logger.error(f"Error buscando UUID: {e}")
            return None

    async def _cleanup_after(self, uuid: str, delay: float):
        await asyncio.sleep(delay)
        try:
            await self.sdk.conn.datachannel.pub_sub.publish_request_new(
                "rt/api/audiohub/request",
                {
                    "api_id": AUDIO_API["SELECT_DELETE"],
                    "parameter": json.dumps({"unique_id": uuid}),
                },
            )
        except Exception:
            pass

    async def list_files(self) -> list:
        """Devuelve la lista de archivos de audio guardados en el robot."""
        if not self.sdk.is_connected:
            return []
        try:
            response = await self.sdk.conn.datachannel.pub_sub.publish_request_new(
                "rt/api/audiohub/request",
                {"api_id": AUDIO_API["GET_AUDIO_LIST"], "parameter": json.dumps({})},
            )
            data_str = response.get('data', {}).get('data', '{}')
            return json.loads(data_str).get('audio_list', [])
        except Exception as e:
            logger.error(f"AudioService.list_files error: {e}")
            return []

    async def clear_all_files(self) -> int:
        """Borra todos los archivos de audio del robot. Devuelve cuántos borró."""
        files = await self.list_files()
        deleted = 0
        for f in files:
            uid = f.get('UNIQUE_ID')
            if not uid:
                continue
            try:
                await self.sdk.conn.datachannel.pub_sub.publish_request_new(
                    "rt/api/audiohub/request",
                    {"api_id": AUDIO_API["SELECT_DELETE"], "parameter": json.dumps({"unique_id": uid})},
                )
                deleted += 1
            except Exception:
                pass
        if deleted:
            logger.info(f"Borrados {deleted} archivos de audio del robot")
        return deleted

    async def set_volume(self, level: int):
        if not self.sdk.is_connected:
            return
        try:
            await self.sdk.conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["VUI"],
                {"api_id": 1006, "parameter": {"volume": max(0, min(100, int(level)))}},
            )
        except Exception as e:
            logger.error(f"AudioService.set_volume error: {e}")
