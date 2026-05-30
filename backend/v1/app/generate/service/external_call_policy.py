"""Shared external-provider behavior knobs for generation tasks."""
from backend.v1.app.config.config import settings


ALLOW_DEGRADED_AUDIO = bool(getattr(settings, "ALLOW_DEGRADED_AUDIO", False))
TTS_TIMEOUT_SECONDS = 30
IMAGE_TIMEOUT_SECONDS = 60
VIDEO_PROVIDER_TIMEOUT_SECONDS = 300
