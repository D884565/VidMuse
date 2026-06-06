"""持久化音视频合并服务。"""
from __future__ import annotations

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
from backend.v1.app.generate.tasks.celery_app import celery_app
from backend.v1.app.models.asset import Asset
from backend.ffmpeg import ffmpeg_tool
from backend.v1.app.push.service.task_event_service import task_event_service

logger = logging.getLogger(__name__)

MERGE_TASK_NAMES = {
    "audio_replace": "merge_replace_audio_task",
    "bgm": "merge_add_bgm_task",
    "mix": "merge_mix_audio_task",
}


class MergeService:
    """持久化合并任务编排。"""

    async def replace_audio(self, db: AsyncSession, video_id: int, audio_id: int) -> dict:
        video = await self._get_asset(db, video_id)
        await self._get_asset(db, audio_id)
        task = self._create_task(
            db,
            task_type="audio_replace",
            video_id=video_id,
            params={"video_id": video_id, "audio_id": audio_id},
            user_id=getattr(video, "user_id", None),
        )
        self._dispatch_task(task["task_id"], "audio_replace")
        return {
            "task_id": task["task_id"],
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
        video = await self._get_asset(db, video_id)
        await self._get_asset(db, bgm_id)
        task = self._create_task(
            db,
            task_type="bgm",
            video_id=video_id,
            params={
                "video_id": video_id,
                "bgm_id": bgm_id,
                "bgm_volume": bgm_volume,
                "original_volume": original_volume,
            },
            user_id=getattr(video, "user_id", None),
        )
        self._dispatch_task(task["task_id"], "bgm")
        return {
            "task_id": task["task_id"],
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
        video = await self._get_asset(db, video_id)
        for audio_id in audio_ids:
            await self._get_asset(db, audio_id)
        task = self._create_task(
            db,
            task_type="mix",
            video_id=video_id,
            params={"video_id": video_id, "audio_ids": audio_ids, "volumes": volumes},
            user_id=getattr(video, "user_id", None),
        )
        self._dispatch_task(task["task_id"], "mix")
        return {
            "task_id": task["task_id"],
            "video_id": video_id,
            "audio_ids": audio_ids,
            "status": "queued",
        }

    async def get_task_status(self, db: AsyncSession, task_id: str) -> dict:
        snapshot = await task_event_service.get_task_snapshot(db, task_id)
        return {
            "task_id": snapshot["task_id"],
            "task_type": snapshot.get("task_type"),
            "status": self._normalize_status(snapshot.get("status")),
            "result": snapshot.get("result"),
            "error_message": snapshot.get("error_message"),
            "created_at": snapshot.get("created_at"),
            "updated_at": snapshot.get("finished_at") or snapshot.get("created_at"),
        }

    async def cancel_task(self, db: AsyncSession, task_id: str) -> dict:
        task = await self.get_task_status(db, task_id)
        if task["status"] not in ("queued", "processing", "running"):
            raise ValueError(f"merge task cannot be cancelled in status: {task['status']}")
        task_event_service.emit_event_sync(
            db=db.sync_session,
            task_id=task_id,
            task_domain="merge",
            task_type=task.get("task_type") or "unknown",
            event_type="task_cancelled",
            status="cancelled",
        )
        await db.commit()
        celery_app.control.revoke(task_id, terminate=False)
        return {
            "task_id": task_id,
            "status": "cancelled",
            "message": "merge task cancelled",
        }

    async def run_dispatched_task(self, task_id: str) -> None:
        async with SessionLocal() as session:
            snapshot = await task_event_service.get_task_snapshot(session, task_id)
            if snapshot.get("status") == "cancelled":
                return
            task_type = snapshot.get("task_type") or "unknown"
            params = await self._get_task_params(session, task_id)
            task_event_service.emit_event_sync(
                db=session.sync_session,
                task_id=task_id,
                task_domain="merge",
                task_type=task_type,
                event_type="task_started",
                status="running",
                progress=0,
                asset_id=snapshot.get("asset_id"),
                trace_id=snapshot.get("trace_id"),
            )
            await session.commit()

            video = await self._get_asset(session, int(params["video_id"]))

            if task_type == "audio_replace":
                audio = await self._get_asset(session, int(params["audio_id"]))
                await self._execute_replace_audio(task_id, video.url, audio.url)
                return

            if task_type == "bgm":
                bgm = await self._get_asset(session, int(params["bgm_id"]))
                await self._execute_add_bgm(
                    task_id,
                    video.url,
                    bgm.url,
                    float(params.get("bgm_volume", 0.3)),
                    float(params.get("original_volume", 1.0)),
                )
                return

            if task_type == "mix":
                audio_urls = []
                for audio_id in params.get("audio_ids", []):
                    audio = await self._get_asset(session, int(audio_id))
                    audio_urls.append(audio.url)
                await self._execute_mix_audio(
                    task_id,
                    video.url,
                    audio_urls,
                    params.get("volumes"),
                )
                return

            await self._update_task_status(
                task_id,
                "failed",
                error_message=f"unsupported merge task type: {task_type}",
            )

    def _create_task(
        self,
        db: AsyncSession,
        *,
        task_type: str,
        video_id: int,
        params: dict,
        user_id: int | None = None,
    ) -> dict:
        return task_event_service.create_task_sync(
            db=db.sync_session,
            user_id=user_id,
            task_domain="merge",
            task_type=task_type,
            asset_id=video_id,
            status="queued",
            extra=params,
        )

    @staticmethod
    def _normalize_status(status: str | None) -> str | None:
        if status == "succeeded":
            return "completed"
        if status == "running":
            return "processing"
        return status

    def _dispatch_task(self, task_id: str, task_type: str) -> None:
        task_name = MERGE_TASK_NAMES[task_type]
        celery_app.send_task(task_name, args=[task_id], task_id=task_id)

    async def _get_task_params(self, db: AsyncSession, task_id: str) -> dict:
        events = await task_event_service.get_task_events(db, task_id)
        for event in events:
            if event.event_type == "task_created":
                return event.result or {}
        raise ValueError(f"merge task params not found: {task_id}")

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
            await asyncio.to_thread(ffmpeg_tool.replace_audio, video_local, audio_local, output_path)
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
                ffmpeg_tool.add_bgm,
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
                ffmpeg_tool.mix_audio_tracks,
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
            snapshot = await task_event_service.get_task_snapshot(session, task_id)
            event_type = "task_progress"
            normalized = status
            if status == "completed":
                event_type = "task_succeeded"
                normalized = "succeeded"
            elif status == "failed":
                event_type = "task_failed"
            task_event_service.emit_event_sync(
                db=session.sync_session,
                task_id=task_id,
                task_domain="merge",
                task_type=snapshot.get("task_type") or "unknown",
                event_type=event_type,
                status=normalized,
                progress=100 if status in {"completed", "failed"} else None,
                asset_id=snapshot.get("asset_id"),
                trace_id=snapshot.get("trace_id"),
                result=result,
                error={"message": error_message} if error_message is not None else None,
            )
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

merge_service = MergeService()
