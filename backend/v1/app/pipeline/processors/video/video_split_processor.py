from typing import Dict, List
import io
import tempfile

from backend.framework.trace import trace
from backend.store import get_storage_client
from backend.v1.app.pipeline.base import BaseProcessor, PipelineContext, constants
from backend.ffmpeg import FFmpegVideoTool
from backend.v1.app.assets.dao import AssetDAO
import logging

logger = logging.getLogger(__name__)

class VideoSplitProcessor(BaseProcessor):
    """
    视频拆分处理器
    将长视频拆分为多个短视频片段
    """

    def __init__(self, slice_duration: int = 15000):
        """
        初始化视频拆分处理器

        :param slice_duration: 每个片段的时长，单位毫秒，默认15秒
        """
        self.slice_duration = slice_duration

    @trace
    def process(self, context: PipelineContext) -> PipelineContext:
        """
        执行视频拆分逻辑

        :param context: 流水线上下文
        :return: 修改后的上下文，包含拆分后的片段url列表
        """
        from backend.store.database.sync_database import get_db

        # 获取数据库会话
        db = next(get_db())
        try:
            # 先获取视频（素材）id，从对象存储中查出来，写入磁盘分割，然后再上传对象存储，最后返回的是对象存储的url
            # 优先从上下文中获取asset_id，如果没有则尝试video_id
            asset_id = context.get("asset_id") or context.get(constants.VIDEO_ID)
            if not asset_id:
                raise ValueError("asset_id or video_id is required in context")

            asset = AssetDAO.get_asset_by_id(db, asset_id)
            if not asset:  # 素材不存在
                raise ValueError(f"Asset {asset_id} not found")
            storage_url = asset.url
            object_name = extract_tos_path(storage_url)
            if not object_name:
                raise ValueError("Failed to extract object name from storage URL")

            client = get_storage_client()
            video_bytes = client.get_object(object_name)

        # 初始化FFmpeg工具，使用临时目录，自动清理
            with tempfile.TemporaryDirectory(prefix="video_split_") as temp_dir:
                ffmpeg_tool = FFmpegVideoTool(temp_dir=temp_dir, auto_cleanup=True)

                # 将字节流写入临时文件
                video_path = ffmpeg_tool.bytes_to_file(video_bytes, suffix=".mp4")

                # 分割视频，保留在磁盘上（不加载到内存）
                segments = ffmpeg_tool.split_video(
                video_path=video_path,
                segment_duration=self.slice_duration / 1000,  # 转换为秒
                extract_first_frame=False,  # 不需要提取首帧
                load_as_bytes=False,  # 不加载到内存，保留在磁盘上
                keep_files=True  # 保留分割后的文件
                )
                slices = list()
                idx = 0
                slices_video_name = list()
                uploaded_slices = []  # 记录已成功上传的分片，用于失败回滚

                try:
                    # todo 后续异步落库
                    for segment in segments:
                        if not segment.segment_path:
                            logger.warning(f"跳过空的视频片段 {idx}")
                            continue

                    # 对象存储name
                        slice_chunk_name = object_name + f"_slice_{idx}.mp4"
                        slices_video_name.append(slice_chunk_name)

                    # 从磁盘文件上传到对象存储（在临时目录删除前完成上传）
                        slice_url = client.upload_file(segment.segment_path, slice_chunk_name)
                        slices.append(slice_url)
                        uploaded_slices.append(slice_chunk_name)  # 记录已上传的分片

                        idx += 1
                except Exception as e:
                # 上传失败，回滚删除已上传的分片
                    logger.error(f"视频分片上传失败，开始回滚已上传的{len(uploaded_slices)}个分片")
                    for uploaded_slice in uploaded_slices:
                        try:
                            client.delete_object(uploaded_slice)
                            logger.debug(f"已删除失败分片: {uploaded_slice}")
                        except Exception as delete_e:
                            logger.warning(f"删除失败分片{uploaded_slice}时出错: {str(delete_e)}")
                # 重新抛出原始异常
                    raise ValueError(f"视频分片上传失败，已回滚已上传分片: {str(e)}") from e

                context.set(constants.SLICE_COUNT, len(slices))
                context.set(constants.SLICES_URL, slices)
                context.set(constants.SLICES_OBJECT_NAME, slices_video_name)

                # 确保video_id保留在上下文中，供后续向量化处理器使用
                if constants.VIDEO_ID not in context.data and asset_id:
                    context.set(constants.VIDEO_ID, asset_id)

                return context
        finally:
            logger.info(f"视频拆分处理器完成，asset_id={asset_id}")


from urllib.parse import urlparse

def extract_tos_path(tos_url: str) -> str:
    """
    仅处理火山引擎 TOS 标准 URL：https://bucket.tos-region.volces.com/object/key
    提取存储路径：object/key
    """
    if not tos_url:
        return ""
    
    parsed = urlparse(tos_url)
    return parsed.path.lstrip("/")  # 去掉开头的 /
