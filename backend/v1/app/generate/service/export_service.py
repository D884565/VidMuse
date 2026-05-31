"""Project export helpers for direct browser downloads."""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse

import requests
from requests import Response as RequestsResponse


class ExportDownloadError(RuntimeError):
    """Raised when the finished video cannot be downloaded."""


@dataclass(slots=True)
class ExportDownloadStream:
    response: RequestsResponse
    filename: str
    media_type: str

    def iter_bytes(self, chunk_size: int = 1024 * 1024):
        try:
            for chunk in self.response.iter_content(chunk_size=chunk_size):
                if chunk:
                    yield chunk
        finally:
            self.response.close()


class ExportService:
    def build_filename(self, project_title: str | None, project_id: int) -> str:
        raw = (project_title or "").strip().replace(" ", "_")
        safe = "".join(ch for ch in raw if ch.isalnum() or ch in {"_", "-"})
        name = safe or f"project_{project_id}"
        if not name.lower().endswith(".mp4"):
            name = f"{name}.mp4"
        return name

    def open_download_stream(self, *, video_url: str, project_title: str | None, project_id: int) -> ExportDownloadStream:
        try:
            response = requests.get(video_url, stream=True, timeout=(10, 300))
            response.raise_for_status()
        except requests.RequestException as exc:
            raise ExportDownloadError(f"failed to download project video: {exc}") from exc

        return ExportDownloadStream(
            response=response,
            filename=self.build_filename(project_title, project_id),
            media_type=self._guess_media_type(video_url),
        )

    def _guess_media_type(self, video_url: str) -> str:
        ext = os.path.splitext(urlparse(video_url).path)[1].lower()
        if ext == ".mov":
            return "video/quicktime"
        if ext == ".webm":
            return "video/webm"
        return "video/mp4"


export_service = ExportService()
