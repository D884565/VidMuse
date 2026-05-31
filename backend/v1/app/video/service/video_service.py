"""视频处理服务。"""
import os
import tempfile
import uuid

import requests
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.v1.app.models.asset import Asset
from backend.v1.app.video.service.ffmpeg_utils import ffmpeg_utils


class VideoService:
    """视频元数据和分割操作，支持本地或远程资源 URL。"""

    async def get_video_info(self, db: AsyncSession, video_id: int) -> dict:
        result = await db.execute(select(Asset).where(Asset.id == video_id))
        asset = result.scalar_one_or_none()
        if not asset:
            raise ValueError(f"视频不存在: {video_id}")

        local_path, is_temp = self._resolve_local_path(asset.url)
        try:
            info = ffmpeg_utils.get_video_info(local_path)
        finally:
            if is_temp:
                self._cleanup_file(local_path)

        return {
            "video_id": video_id,
            "duration": info["duration"],
            "width": info["width"],
            "height": info["height"],
            "format": info["format"],
            "file_size": info["file_size"],
            "fps": info["fps"],
        }

    async def split_video(
        self, db: AsyncSession, video_id: int, timestamps: list[float]
    ) -> dict:
        result = await db.execute(select(Asset).where(Asset.id == video_id))
        asset = result.scalar_one_or_none()
        if not asset:
            raise ValueError(f"视频不存在: {video_id}")

        local_path, is_temp = self._resolve_local_path(asset.url)
        try:
            info = ffmpeg_utils.get_video_info(local_path)
            duration = info["duration"]

            sorted_timestamps = sorted(timestamps)
            if sorted_timestamps and sorted_timestamps[-1] > duration:
                raise ValueError(f"时间戳超出视频时长: {duration}")

            output_dir = os.path.join(
                tempfile.gettempdir(),
                f"video_splits_{video_id}_{uuid.uuid4().hex[:8]}",
            )
            os.makedirs(output_dir, exist_ok=True)

            all_timestamps = [0.0] + sorted_timestamps + [None]
            segments = []
            for i in range(len(all_timestamps) - 1):
                start = all_timestamps[i]
                end = all_timestamps[i + 1]
                output_file = os.path.join(output_dir, f"{video_id}_segment_{i:03d}.mp4")
                ffmpeg_utils.split_video(local_path, output_file, start, end)
                segments.append({
                    "index": i,
                    "start": start,
                    "end": end,
                    "file": output_file,
                })

            return {
                "video_id": video_id,
                "duration": duration,
                "segments": segments,
                "total_segments": len(segments),
            }
        finally:
            if is_temp:
                self._cleanup_file(local_path)

    def _resolve_local_path(self, url: str | None) -> tuple[str, bool]:
        if not url:
            raise ValueError("视频文件URL为空")
        if url.startswith(("http://", "https://")):
            return self._download_to_temp(url), True
        if not os.path.exists(url):
            raise ValueError(f"视频文件不存在: {url}")
        return url, False

    def _download_to_temp(self, url: str) -> str:
        suffix = os.path.splitext(url.split("?")[0])[1] or ".mp4"
        fd, local_path = tempfile.mkstemp(prefix="video_asset_", suffix=suffix)
        os.close(fd)
        try:
            with requests.get(url, stream=True, timeout=120) as response:
                response.raise_for_status()
                with open(local_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
            return local_path
        except Exception:
            self._cleanup_file(local_path)
            raise

    @staticmethod
    def _cleanup_file(path: str):
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except OSError:
            pass


video_service = VideoService()
