"""TTS 语音合成服务工具。"""
import base64
import logging
import os
import tempfile
import time
import uuid
from dataclasses import dataclass

import requests

from backend.v1.app.config.config import settings
from backend.v1.app.generate.service.external_call_policy import TTS_TIMEOUT_SECONDS
from backend.ffmpeg import ffmpeg_tool

logger = logging.getLogger(__name__)

TTS_API_URL = "https://openspeech.bytedance.com/api/v1/tts"


@dataclass
class TtsResult:
    path: str
    fallback_used: bool
    provider: str
    warning: str | None = None


class TtsService:
    def __init__(self):
        self.temp_dir = tempfile.gettempdir()
        self.app_id = settings.TTS_ACCESS_KEY
        self.token = settings.TTS_SECRET_KEY
        self.last_fallback = False

    def generate_audio(self, text: str, voice_type: str = "zh_female_cancan_mars_bigtts") -> TtsResult:
        try:
            self.last_fallback = False
            return TtsResult(
                path=self._call_volcano_tts(text, voice_type),
                fallback_used=False,
                provider="volcano_tts",
            )
        except Exception as exc:
            logger.warning("[TTS] provider failed, using silent fallback: %s", exc)
            self.last_fallback = True
            return TtsResult(
                path=self._create_silent_audio(text),
                fallback_used=True,
                provider="silent_fallback",
                warning=str(exc),
            )

    def create_silent_audio_for_duration(self, duration_sec: float) -> str:
        output_path = os.path.join(self.temp_dir, f"tts_{uuid.uuid4().hex}.mp3")
        return ffmpeg_tool.create_silent_audio_for_duration(
            duration_sec, output_path=output_path,
        )

    def fit_audio_to_duration(self, input_path: str, duration_sec: float) -> str:
        output_path = os.path.join(self.temp_dir, f"tts_{uuid.uuid4().hex}_fit.mp3")
        return ffmpeg_tool.fit_audio_to_duration(
            input_path, duration_sec, output_path=output_path,
        )

    def concat_audio_clips(self, audio_paths: list[str]) -> str:
        output_path = os.path.join(self.temp_dir, f"tts_{uuid.uuid4().hex}_merged.mp3")
        return ffmpeg_tool.concat_audio_clips(audio_paths, output_path=output_path)

    def _call_volcano_tts(self, text: str, voice_type: str) -> str:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer;{self.token}",
        }
        payload = {
            "app": {
                "appid": self.app_id,
                "token": "fake_token",
                "cluster": "volcano_tts",
            },
            "user": {"uid": "vidmuse_user"},
            "audio": {
                "voice_type": voice_type,
                "encoding": "mp3",
                "speed_ratio": 1.0,
                "volume_ratio": 1.0,
            },
            "request": {
                "reqid": uuid.uuid4().hex,
                "text": text,
                "operation": "query",
            },
        }
        response = self._request_with_retry(TTS_API_URL, json=payload, headers=headers)
        response.raise_for_status()
        resp_data = response.json()
        if resp_data.get("code") != 3000:
            raise RuntimeError(f"TTS API returned error: {resp_data.get('message', 'unknown error')}")

        audio_base64 = resp_data.get("data", "")
        if not audio_base64:
            raise RuntimeError("TTS API returned empty audio data")

        audio_bytes = base64.b64decode(audio_base64)
        output_path = os.path.join(self.temp_dir, f"tts_{uuid.uuid4().hex}.mp3")
        with open(output_path, "wb") as handle:
            handle.write(audio_bytes)
        logger.info("[TTS] provider call succeeded: %s", output_path)
        return output_path

    def _request_with_retry(self, url: str, *, json: dict, headers: dict, attempts: int = 3) -> requests.Response:
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                return requests.request(
                    "POST",
                    url,
                    json=json,
                    headers=headers,
                    timeout=TTS_TIMEOUT_SECONDS,
                )
            except requests.RequestException as exc:
                last_error = exc
                if attempt >= attempts:
                    break
                time.sleep(0.5 * attempt)
        raise RuntimeError(f"TTS request failed after {attempts} attempts: {last_error}")

    def _create_silent_audio(self, text: str) -> str:
        duration_sec = max(1, len(text) // 4)
        return self.create_silent_audio_for_duration(duration_sec)


tts_service = TtsService()
