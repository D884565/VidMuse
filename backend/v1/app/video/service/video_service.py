"""视频处理服务"""
import os
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.v1.app.models.asset import Asset
from backend.v1.app.video.service.ffmpeg_utils import ffmpeg_utils


class VideoService:
    """视频处理服务"""

    async def get_video_info(self, db: AsyncSession, video_id: int) -> dict:
        """
        获取视频元数据信息

        Args:
            db: 数据库会话
            video_id: 视频文件ID

        Returns:
            视频信息字典
        """
        # 查询视频资产
        result = await db.execute(select(Asset).where(Asset.id == video_id))
        asset = result.scalar_one_or_none()
        if not asset:
            raise ValueError(f"视频不存在: {video_id}")

        # 检查文件是否存在
        if not asset.url or not os.path.exists(asset.url):
            raise ValueError(f"视频文件不存在: {video_id}")

        # 使用 FFmpeg 获取视频信息
        info = ffmpeg_utils.get_video_info(asset.url)
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
        """
        按时间戳分段视频

        Args:
            db: 数据库会话
            video_id: 视频文件ID
            timestamps: 时间戳列表

        Returns:
            分段结果
        """
        # 查询视频资产
        result = await db.execute(select(Asset).where(Asset.id == video_id))
        asset = result.scalar_one_or_none()
        if not asset:
            raise ValueError(f"视频不存在: {video_id}")

        # 检查文件是否存在
        if not asset.url or not os.path.exists(asset.url):
            raise ValueError(f"视频文件不存在: {video_id}")

        # 获取视频时长
        info = ffmpeg_utils.get_video_info(asset.url)
        duration = info["duration"]

        # 验证时间戳
        sorted_timestamps = sorted(timestamps)
        if sorted_timestamps[-1] > duration:
            raise ValueError(f"时间戳超出视频时长: {duration}")

        # 创建输出目录
        output_dir = os.path.join(os.path.dirname(asset.url), "splits")
        os.makedirs(output_dir, exist_ok=True)

        # 构建完整的时间点列表（包括开始和结束）
        all_timestamps = [0.0] + sorted_timestamps + [None]

        segments = []
        for i in range(len(all_timestamps) - 1):
            start = all_timestamps[i]
            end = all_timestamps[i + 1]

            # 生成输出文件名
            output_file = os.path.join(output_dir, f"{video_id}_segment_{i:03d}.mp4")

            # 执行分段
            ffmpeg_utils.split_video(asset.url, output_file, start, end)
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


video_service = VideoService()
