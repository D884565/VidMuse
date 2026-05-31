"""持久化音视频合并服务。"""
import asyncio
import json
import logging
import os
import tempfile
import uuid

import aiohttp
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.store.database.async_database import SessionLocal
from backend.store.obj.factory import get_storage_client
from backend.v1.app.generate.temp.celery_app import celery_app
from backend.v1.app.models.asset import Asset
from backend.v1.app.models.merge_task import MergeTask
from backend.v1.app.video.service.ffmpeg_utils import ffmpeg_utils

logger = logging.getLogger(__name__)

MERGE_TASK_NAMES = {
    "audio_replace": "merge_replace_audio_task",
    "bgm": "merge_add_bgm_task",
    "mix": "merge_mix_audio_task",
}


class MergeService:
    """持久化合并任务编排。"""

    async def replace_audio(self, db: AsyncSession, video_id: int, audio_id: int) -> dict:
        await self._get_asset(db, video_id)
        await self._get_asset(db, audio_id)
        task = await self._create_task(
            db,
            task_type="audio_replace",
            video_id=video_id,
            params={"audio_id": audio_id},
        )
        self._dispatch_task(task.task_id, task.task_type)
        return {
            "task_id": task.task_id,
            "video_id": video_id,
            "audio_id": audio_id,
            "status": "queued",
        }

    async def add_bgm(
        self,
        db: AsyncSession,
        video_id: int,
        bgm_id: int,
        bgm_volume: float = 0.3,
        original_volume: float = 1.0,
    ) -> dict:
        await self._get_asset(db, video_id)
        await self._get_asset(db, bgm_id)
        task = await self._create_task(
            db,
            task_type="bgm",
            video_id=video_id,
            params={
                "bgm_id": bgm_id,
                "bgm_volume": bgm_volume,
                "original_volume": original_volume,
            },
        )
        self._dispatch_task(task.task_id, task.task_type)
        return {
            "task_id": task.task_id,
            "video_id": video_id,
            "bgm_id": bgm_id,
            "status": "queued",
        }

    async def mix_audio_tracks(
        self,
        db: AsyncSession,
        video_id: int,
        audio_ids: list[int],
        volumes: list[float] | None = None,
    ) -> dict:
        await self._get_asset(db, video_id)
        for audio_id in audio_ids:
            await self._get_asset(db, audio_id)
        task = await self._create_task(
            db,
            task_type="mix",
            video_id=video_id,
            params={"audio_ids": audio_ids, "volumes": volumes},
        )
        self._dispatch_task(task.task_id, task.task_type)
        return {
            "task_id": task.task_id,
            "video_id": video_id,
            "audio_ids": audio_ids,
            "status": "queued",
        }

    async def get_task_status(self, db: AsyncSession, task_id: str) -> dict:
        task = await self._fetch_task(db, task_id)
        return self._task_to_dict(task)

    async def cancel_task(self, db: AsyncSession, task_id: str) -> dict:
        task = await self._fetch_task(db, task_id)
        if task.status not in ("queued", "processing"):
            raise ValueError(f"merge task cannot be cancelled in status: {task.status}")
        task.status = "cancelled"
        await db.commit()
        celery_app.control.revoke(task_id, terminate=False)
        return {
            "task_id": task.task_id,
            "status": "cancelled",
            "message": "merge task cancelled",
        }

    async def run_dispatched_task(self, task_id: str) -> None:
        async with SessionLocal() as session:
            task = await self._fetch_task(session, task_id)
            if task.status == "cancelled":
                return
            task.status = "processing"
            await session.commit()

            video = await self._get_asset(session, task.video_id)
            params = json.loads(task.params or "{}")

            if task.task_type == "audio_replace":
                audio = await self._get_asset(session, int(params["audio_id"]))
                await self._execute_replace_audio(task.task_id, video.url, audio.url)
                return

            if task.task_type == "bgm":
                bgm = await self._get_asset(session, int(params["bgm_id"]))
                await self._execute_add_bgm(
                    task.task_id,
                    video.url,
                    bgm.url,
                    float(params.get("bgm_volume", 0.3)),
                    float(params.get("original_volume", 1.0)),
                )
                return

            if task.task_type == "mix":
                audio_urls = []
                for audio_id in params.get("audio_ids", []):
                    audio = await self._get_asset(session, int(audio_id))
                    audio_urls.append(audio.url)
                await self._execute_mix_audio(
                    task.task_id,
                    video.url,
                    audio_urls,
                    params.get("volumes"),
                )
                return

            await self._update_task_status(
                task.task_id,
                "failed",
                error_message=f"unsupported merge task type: {task.task_type}",
            )

    async def _create_task(
        self,
        db: AsyncSession,
        *,
        task_type: str,
        video_id: int,
        params: dict,
    ) -> MergeTask:
        task = MergeTask(
            task_id=f"merge_{uuid.uuid4().hex[:16]}",
            task_type=task_type,
            video_id=video_id,
            params=json.dumps(params),
            status="queued",
        )
        db.add(task)
        await db.commit()
        return task

    def _dispatch_task(self, task_id: str, task_type: str) -> None:
        task_name = MERGE_TASK_NAMES[task_type]
        celery_app.send_task(task_name, args=[task_id], task_id=task_id)

    async def _fetch_task(self, db: AsyncSession, task_id: str) -> MergeTask:
        result = await db.execute(select(MergeTask).where(MergeTask.task_id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            raise ValueError(f"merge task not found: {task_id}")
        return task

    async def _execute_replace_audio(self, task_id: str, video_path: str, audio_path: str) -> None:
        temp_files: list[str] = []
        try:
            video_local, video_is_temp = await self._resolve_local_path(video_path)
            if video_is_temp:
                temp_files.append(video_local)
            audio_local, audio_is_temp = await self._resolve_local_path(audio_path)
            if audio_is_temp:
                temp_files.append(audio_local)
            output_path = self._generate_output_path(video_local, "replaced")
            await asyncio.to_thread(ffmpeg_utils.replace_audio, video_local, audio_local, output_path)
            output_url = self._upload_to_storage(output_path, task_id, "replaced")
            self._cleanup_temp_files([output_path])
            await self._update_task_status(task_id, "completed", {"output_url": output_url})
        except Exception as exc:
            await self._update_task_status(task_id, "failed", error_message=str(exc))
        finally:
            self._cleanup_temp_files(temp_files)

    async def _execute_add_bgm(
        self,
        task_id: str,
        video_path: str,
        bgm_path: str,
        bgm_volume: float,
        original_volume: float,
    ) -> None:
        temp_files: list[str] = []
        try:
            video_local, video_is_temp = await self._resolve_local_path(video_path)
            if video_is_temp:
                temp_files.append(video_local)
            bgm_local, bgm_is_temp = await self._resolve_local_path(bgm_path)
            if bgm_is_temp:
                temp_files.append(bgm_local)
            output_path = self._generate_output_path(video_local, "bgm")
            await asyncio.to_thread(
                ffmpeg_utils.add_bgm,
                video_local,
                bgm_local,
                output_path,
                bgm_volume,
                original_volume,
            )
            output_url = self._upload_to_storage(output_path, task_id, "bgm")
            self._cleanup_temp_files([output_path])
            await self._update_task_status(task_id, "completed", {"output_url": output_url})
        except Exception as exc:
            await self._update_task_status(task_id, "failed", error_message=str(exc))
        finally:
            self._cleanup_temp_files(temp_files)

    async def _execute_mix_audio(
        self,
        task_id: str,
        video_path: str,
        audio_paths: list[str],
        volumes: list[float] | None,
    ) -> None:
        temp_files: list[str] = []
        try:
            video_local, video_is_temp = await self._resolve_local_path(video_path)
            if video_is_temp:
                temp_files.append(video_local)
            local_audio_paths = []
            for audio_path in audio_paths:
                local_path, is_temp = await self._resolve_local_path(audio_path)
                if is_temp:
                    temp_files.append(local_path)
                local_audio_paths.append(local_path)
            output_path = self._generate_output_path(video_local, "mixed")
            await asyncio.to_thread(
                ffmpeg_utils.mix_audio_tracks,
                video_local,
                local_audio_paths,
                output_path,
                volumes,
            )
            output_url = self._upload_to_storage(output_path, task_id, "mixed")
            self._cleanup_temp_files([output_path])
            await self._update_task_status(task_id, "completed", {"output_url": output_url})
        except Exception as exc:
            await self._update_task_status(task_id, "failed", error_message=str(exc))
        finally:
            self._cleanup_temp_files(temp_files)

    async def _update_task_status(
        self,
        task_id: str,
        status: str,
        result: dict | None = None,
        error_message: str | None = None,
    ) -> None:
        async with SessionLocal() as session:
            task = await self._fetch_task(session, task_id)
            task.status = status
            if result is not None:
                task.result = json.dumps(result)
            if error_message is not None:
                task.error_message = error_message
            await session.commit()

    async def _get_asset(self, db: AsyncSession, asset_id: int) -> Asset:
        result = await db.execute(select(Asset).where(Asset.id == asset_id))
        asset = result.scalar_one_or_none()
        if not asset:
            raise ValueError(f"asset not found: {asset_id}")
        if not asset.url:
            raise ValueError(f"asset url missing: {asset_id}")
        return asset

    async def _resolve_local_path(self, url: str) -> tuple[str, bool]:
        if url.startswith(("http://", "https://")):
            return await self._download_to_temp(url), True
        if not os.path.exists(url):
            raise ValueError(f"file not found: {url}")
        return url, False

    async def _download_to_temp(self, url: str) -> str:
        ext = os.path.splitext(url.split("?")[0])[1] or ".tmp"
        fd, local_path = tempfile.mkstemp(prefix="merge_", suffix=ext)
        os.close(fd)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=300)) as response:
                    if response.status != 200:
                        raise ValueError(f"download failed: HTTP {response.status} for {url}")
                    with open(local_path, "wb") as file_obj:
                        async for chunk in response.content.iter_chunked(8192):
                            file_obj.write(chunk)
            return local_path
        except Exception:
            if os.path.exists(local_path):
                os.unlink(local_path)
            raise

    @staticmethod
    def _cleanup_temp_files(paths: list[str]) -> None:
        for path in paths:
            try:
                if path and os.path.exists(path):
                    os.unlink(path)
            except OSError:
                pass

    def _generate_output_path(self, video_path: str, suffix: str) -> str:
        directory = os.path.dirname(video_path) or tempfile.gettempdir()
        name, ext = os.path.splitext(os.path.basename(video_path))
        return os.path.join(directory, f"{name}_{suffix}_{uuid.uuid4().hex[:8]}{ext}")

    def _upload_to_storage(self, local_path: str, task_id: str, suffix: str) -> str:
        ext = os.path.splitext(local_path)[1] or ".mp4"
        object_key = f"merge/{task_id}/{suffix}_{uuid.uuid4().hex[:8]}{ext}"
        return get_storage_client().upload_file(local_path, object_key)

    def _task_to_dict(self, task: MergeTask) -> dict:
        return {
            "task_id": task.task_id,
            "task_type": task.task_type,
            "video_id": task.video_id,
            "status": task.status,
            "result": json.loads(task.result) if task.result else None,
            "error_message": task.error_message,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        }


merge_service = MergeService()
