from typing import Dict, List, Any
import json
import logging

from backend.framework.trace import trace
from backend.v1.app.pipeline.base import BaseProcessor, PipelineContext

logger = logging.getLogger(__name__)


class VideoProductUnderstandingProcessor(BaseProcessor):
    """
    视频商品理解处理器
    调用视频解析流水线处理商品视频，提取结构化信息并转换为商品理解格式
    输出格式与图片/文本理解保持一致，方便后续统一处理
    """

    def __init__(self):
        """
        初始化视频商品理解处理器
        """
        # 初始化视频解析流水线，禁用向量化
        from backend.v1.app.pipeline import VideoParsingPipeline
        self.video_pipeline = VideoParsingPipeline(
            enable_vectorization=False,  # 不需要向量化
            enable_persistence=False  # 不需要持久化执行记录
        )

    @trace
    def process(self, context: PipelineContext) -> PipelineContext:
        """
        执行视频商品理解逻辑
        调用视频解析流水线获取视频结构化信息，转换为商品理解格式

        输入（从上下文获取）：
        - video_id: str 视频ID
        - video_url: str 视频URL（可选）
        - video_object_name: str 视频对象存储路径（优先使用）
        - video_duration: int 视频时长（毫秒，可选）

        输出（写入上下文）：
        - product_understanding: Dict 商品理解结果，与图片/文本理解格式一致

        :param context: 流水线上下文
        :return: 修改后的上下文
        """
        video_id = context.get("video_id") or context.get("product_id")
        video_object_name = context.get("video_object_name")
        video_url = context.get("video_url")
        video_duration = context.get("video_duration", 0)

        if not video_object_name and not video_url:
            raise ValueError("video_object_name or video_url is required for video processing")
        if not video_id:
            raise ValueError("video_id or product_id is required")

        try:
            # 构建视频流水线输入
            pipeline_input = {
                "video_id": video_id,
                "object_name": video_object_name,
                "video_url": video_url,
                "video_duration": video_duration
            }

            # 运行视频解析流水线
            logger.info(f"开始处理商品视频，video_id: {video_id}")
            pipeline_result = self.video_pipeline.run(pipeline_input)

            if not pipeline_result["success"]:
                error_msg = pipeline_result["errors"][0] if pipeline_result["errors"] else "视频解析失败"
                raise ValueError(f"视频解析流水线执行失败: {error_msg}")

            # 从流水线结果中提取视频结构化信息
            pipeline_data = pipeline_result["data"]
            ai_features = pipeline_data.get("ai_features", {})
            video_data = pipeline_data.get("video_data", {})

            # 转换为商品理解格式
            # 从视频整体理解结果中提取商品相关信息
            video_basic_info = ai_features.get("视频基本信息", {})
            product_understanding = {
                "商品名称": video_basic_info.get("商品名称", ""),
                "商品介绍": video_basic_info.get("商品描述", ""),
                "核心卖点": video_basic_info.get("核心卖点", []),
                "目标人群": video_basic_info.get("目标人群", ""),
                "使用场景": video_basic_info.get("使用场景", []),
                "价格信息": {
                    "原价": video_basic_info.get("原价", 0),
                    "现价": video_basic_info.get("现价", 0),
                    "优惠信息": video_basic_info.get("优惠信息", "")
                },
                "商品参数": video_basic_info.get("商品参数", {}),
                "视频分析": {
                    "视频时长": video_duration,
                    "分片数量": pipeline_data.get("slice_count", 0),
                    "整体摘要": video_basic_info.get("视频摘要", "")
                }
            }

            # 存储结果，格式与图片/文本理解完全一致
            context.set("product_understanding", product_understanding)
            logger.info(f"视频商品理解完成，video_id: {video_id}")

        except Exception as e:
            logger.error(f"视频商品理解失败: {str(e)}", exc_info=True)
            context.add_error(ValueError(f"视频商品理解失败: {str(e)}"))

        return context
