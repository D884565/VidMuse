"""音视频合成服务"""
import os
import uuid
import json
import asyncio
import tempfile
import logging
import aiohttp
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.v1.app.models.asset import Asset
from backend.v1.app.models.merge_task import MergeTask
from backend.v1.app.video.service.ffmpeg_utils import ffmpeg_utils

logger = logging.getLogger(__name__)


class MergeService:
    """音视频合成服务"""

    async def replace_audio(
        self, db: AsyncSession, video_id: int, audio_id: int
    ) -> dict:
        """
        替换视频音频

        Args:
            db: 数据库会话
            video_id: 视频文件ID
            audio_id: 音频文件ID

        Returns:
            任务信息
        """
        # 查询视频和音频资产
        video = await self._get_asset(db, video_id)
        audio = await self._get_asset(db, audio_id)

        # 生成任务ID
        task_id = f"merge_{uuid.uuid4().hex[:16]}"

        # 创建任务记录
        task = MergeTask(
            task_id=task_id,
            task_type="audio_replace",
            video_id=video_id,
            params=json.dumps({"audio_id": audio_id}),
            status="queued",
        )
        db.add(task)
        await db.commit()

        # 异步执行合成任务
        asyncio.create_task(
            self._execute_replace_audio(task_id, video.url, audio.url)
        )

        return {
            "task_id": task_id,
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
        """
        添加背景音乐

        Args:
            db: 数据库会话
            video_id: 视频文件ID
            bgm_id: BGM文件ID
            bgm_volume: BGM音量（0-1）
            original_volume: 原音频音量（0-1）

        Returns:
            任务信息
        """
        # 查询视频和BGM资产
        video = await self._get_asset(db, video_id)
        bgm = await self._get_asset(db, bgm_id)

        # 生成任务ID
        task_id = f"merge_{uuid.uuid4().hex[:16]}"

        # 创建任务记录
        task = MergeTask(
            task_id=task_id,
            task_type="bgm",
            video_id=video_id,
            params=json.dumps({
                "bgm_id": bgm_id,
                "bgm_volume": bgm_volume,
                "original_volume": original_volume,
            }),
            status="queued",
        )
        db.add(task)
        await db.commit()

        # 异步执行合成任务
        asyncio.create_task(
            self._execute_add_bgm(
                task_id, video.url, bgm.url,
                bgm_volume, original_volume
            )
        )

        return {
            "task_id": task_id,
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
        """
        混合多个音频轨道

        Args:
            db: 数据库会话
            video_id: 视频文件ID
            audio_ids: 音频文件ID列表
            volumes: 各音频音量列表（0-1）

        Returns:
            任务信息
        """
        # 查询视频资产
        video = await self._get_asset(db, video_id)

        # 查询音频资产
        audio_paths = []
        for audio_id in audio_ids:
            audio = await self._get_asset(db, audio_id)
            audio_paths.append(audio.url)

        # 生成任务ID
        task_id = f"merge_{uuid.uuid4().hex[:16]}"

        # 创建任务记录
        task = MergeTask(
            task_id=task_id,
            task_type="mix",
            video_id=video_id,
            params=json.dumps({
                "audio_ids": audio_ids,
                "volumes": volumes,
            }),
            status="queued",
        )
        db.add(task)
        await db.commit()

        # 异步执行合成任务
        asyncio.create_task(
            self._execute_mix_audio(task_id, video.url, audio_paths, volumes)
        )

        return {
            "task_id": task_id,
            "video_id": video_id,
            "audio_ids": audio_ids,
            "status": "queued",
        }

    async def get_task_status(self, db: AsyncSession, task_id: str) -> dict:
        """
        查询合成任务状态

        Args:
            db: 数据库会话
            task_id: 任务ID

        Returns:
            任务状态
        """
        result = await db.execute(select(MergeTask).where(MergeTask.task_id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            raise ValueError(f"任务不存在: {task_id}")

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

    async def cancel_task(self, db: AsyncSession, task_id: str) -> dict:
        """
        取消合成任务

        Args:
            db: 数据库会话
            task_id: 任务ID

        Returns:
            取消结果
        """
        result = await db.execute(select(MergeTask).where(MergeTask.task_id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            raise ValueError(f"任务不存在: {task_id}")

        if task.status not in ("queued", "processing"):
            raise ValueError(f"任务状态不允许取消: {task.status}")

        task.status = "cancelled"
        await db.commit()

        return {
            "task_id": task.task_id,
            "status": "cancelled",
            "message": "任务已取消",
        }

    async def _execute_replace_audio(
        self, task_id: str, video_path: str, audio_path: str
    ):
        """执行音频替换任务"""
        temp_files = []
        try:
            video_local, video_is_temp = await self._resolve_local_path(video_path)
            if video_is_temp:
                temp_files.append(video_local)
            audio_local, audio_is_temp = await self._resolve_local_path(audio_path)
            if audio_is_temp:
                temp_files.append(audio_local)

            output_path = self._generate_output_path(video_local, "replaced")
            await asyncio.to_thread(
                ffmpeg_utils.replace_audio,
                video_local,
                audio_local,
                output_path,
            )

            await self._update_task_status(task_id, "completed", {
                "output_path": output_path,
            })

        except Exception as e:
            await self._update_task_status(task_id, "failed", error_message=str(e))
        finally:
            self._cleanup_temp_files(temp_files)

    async def _execute_add_bgm(
        self, task_id: str, video_path: str, bgm_path: str,
        bgm_volume: float, original_volume: float
    ):
        """执行添加BGM任务"""
        temp_files = []
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

            await self._update_task_status(task_id, "completed", {
                "output_path": output_path,
            })

        except Exception as e:
            await self._update_task_status(task_id, "failed", error_message=str(e))
        finally:
            self._cleanup_temp_files(temp_files)

    async def _execute_mix_audio(
        self, task_id: str, video_path: str,
        audio_paths: list[str], volumes: list[float] | None
    ):
        """执行音频混合任务"""
        temp_files = []
        try:
            video_local, video_is_temp = await self._resolve_local_path(video_path)
            if video_is_temp:
                temp_files.append(video_local)

            local_audio_paths = []
            for ap in audio_paths:
                local_p, is_temp = await self._resolve_local_path(ap)
                if is_temp:
                    temp_files.append(local_p)
                local_audio_paths.append(local_p)

            output_path = self._generate_output_path(video_local, "mixed")
            await asyncio.to_thread(
                ffmpeg_utils.mix_audio_tracks,
                video_local,
                local_audio_paths,
                output_path,
                volumes,
            )

            await self._update_task_status(task_id, "completed", {
                "output_path": output_path,
            })

        except Exception as e:
            await self._update_task_status(task_id, "failed", error_message=str(e))
        finally:
            self._cleanup_temp_files(temp_files)

    async def _update_task_status(
        self, task_id: str, status: str,
        result: dict | None = None, error_message: str | None = None
    ):
        """更新任务状态"""
        from backend.store.database.async_database import SessionLocal
        async with SessionLocal() as session:
            result_query = await session.execute(
                select(MergeTask).where(MergeTask.task_id == task_id)
            )
            task = result_query.scalar_one_or_none()
            if task:
                task.status = status
                if result:
                    task.result = json.dumps(result)
                if error_message:
                    task.error_message = error_message
                await session.commit()

    async def _get_asset(self, db: AsyncSession, asset_id: int) -> Asset:
        """获取资产"""
        result = await db.execute(select(Asset).where(Asset.id == asset_id))
        asset = result.scalar_one_or_none()
        if not asset:
            raise ValueError(f"资产不存在: {asset_id}")
        if not asset.url:
            raise ValueError(f"资产URL为空: {asset_id}")
        return asset

    async def _resolve_local_path(self, url: str) -> tuple[str, bool]:
        """将URL解析为本地路径。返回 (local_path, is_temp_file)"""
        if url.startswith(("http://", "https://")):
            local_path = await self._download_to_temp(url)
            return local_path, True
        if not os.path.exists(url):
            raise ValueError(f"文件不存在: {url}")
        return url, False

    async def _download_to_temp(self, url: str) -> str:
        """下载远程文件到临时目录"""
        ext = os.path.splitext(url.split("?")[0])[1] or ".tmp"
        fd, local_path = tempfile.mkstemp(suffix=ext, prefix="merge_")
        os.close(fd)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=300)) as resp:
                    if resp.status != 200:
                        raise ValueError(f"下载失败: HTTP {resp.status} for {url}")
                    with open(local_path, "wb") as f:
                        async for chunk in resp.content.iter_chunked(8192):
                            f.write(chunk)
            logger.info(f"已下载远程文件到本地: {url} -> {local_path}")
            return local_path
        except Exception:
            if os.path.exists(local_path):
                os.unlink(local_path)
            raise

    @staticmethod
    def _cleanup_temp_files(paths: list[str]):
        """清理临时文件"""
        for p in paths:
            try:
                if p and os.path.exists(p):
                    os.unlink(p)
            except OSError:
                pass

    def _generate_output_path(self, video_path: str, suffix: str) -> str:
        """生成输出文件路径"""
        directory = os.path.dirname(video_path)
        if not directory:
            directory = tempfile.gettempdir()
        filename = os.path.basename(video_path)
        name, ext = os.path.splitext(filename)
        output_filename = f"{name}_{suffix}_{uuid.uuid4().hex[:8]}{ext}"
        return os.path.join(directory, output_filename)


merge_service = MergeService()
