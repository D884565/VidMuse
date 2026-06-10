"""
流水线工厂类
统一创建各种解析流水线实例，避免重复代码
"""
from typing import Optional

from backend.v1.app.pipeline.pipelines.product_parsing_pipeline import ProductParsingPipeline
from backend.v1.app.pipeline.pipelines.video_parsing_pipeline import VideoParsingPipeline
from backend.v1.app.pipeline.pipelines.audio_parsing_pipeline import AudioParsingPipeline
from backend.v1.app.pipeline.pipelines.video_parsing_ab_pipeline import VideoParsingABPipeline
from backend.v1.app.pipeline.pipelines.direct_video_parsing_pipeline import DirectVideoParsingPipeline
from backend.v1.app.pipeline.base import BasePipeline


class PipelineFactory:
    """流水线工厂类，提供统一的流水线创建接口"""

    @staticmethod
    def get_product_pipeline(
        product_schema_path: Optional[str] = None,
        enable_persistence: bool = True,
        persist_to_asset: bool = True,
        **kwargs
    ) -> ProductParsingPipeline:
        """
        创建商品解析流水线实例
        支持多模态输入：图片、文本、视频的商品内容理解

        :param product_schema_path: 自定义商品校验Schema路径
        :param enable_persistence: 是否开启执行记录持久化
        :param persist_to_asset: 是否将结果落库到asset表
        :return: ProductParsingPipeline实例
        """
        return ProductParsingPipeline(
            product_schema_path=product_schema_path,
            enable_persistence=enable_persistence,
            persist_to_asset=persist_to_asset,
            **kwargs
        )

    @staticmethod
    def get_video_pipeline(
        custom_processors: Optional[list] = None,
        slice_schema_path: Optional[str] = None,
        video_schema_path: Optional[str] = None,
        enable_vectorization: bool = True,
        enable_persistence: bool = True,
        **kwargs
    ) -> VideoParsingPipeline:
        """
        创建视频解析流水线实例
        专用于视频内容理解：视频拆分、分片理解、整体分析、向量化等

        :param custom_processors: 自定义处理器列表
        :param slice_schema_path: 切片校验Schema路径
        :param video_schema_path: 视频整体校验Schema路径
        :param enable_vectorization: 是否启用向量化存储
        :param enable_persistence: 是否开启执行记录持久化
        :return: VideoParsingPipeline实例
        """
        return VideoParsingPipeline(
            custom_processors=custom_processors,
            slice_schema_path=slice_schema_path,
            video_schema_path=video_schema_path,
            enable_vectorization=enable_vectorization,
            enable_persistence=enable_persistence,
            **kwargs
        )

    @staticmethod
    def get_video_ab_pipeline( custom_processors: Optional[list] = None,
        slice_schema_path: Optional[str] = None,
        video_schema_path: Optional[str] = None,
        enable_vectorization: bool = True,
        enable_persistence: bool = True,
        **kwargs) -> VideoParsingABPipeline:
        """
        创建视频解析流水线AB测试版本实例
        使用关键帧+音频识别的理解方式替代原有的视频分片理解方式，后续处理逻辑与原流水线完全一致
        接口与原VideoParsingPipeline完全兼容，可以无缝切换进行AB测试

        :return: VideoParsingABPipeline实例
        """
        return VideoParsingABPipeline( 
            custom_processors=custom_processors,
            slice_schema_path=slice_schema_path,
            video_schema_path=video_schema_path,
            enable_vectorization=enable_vectorization,
            enable_persistence=enable_persistence,
            **kwargs
        )
    
    @staticmethod
    def get_direct_video_pipeline( custom_processors: Optional[list] = None,
        slice_schema_path: Optional[str] = None,
        video_schema_path: Optional[str] = None,
        enable_vectorization: bool = True,
        enable_persistence: bool = True,
        **kwargs) -> DirectVideoParsingPipeline:
        """
        创建极简视频解析流水线实例
        直接理解完整视频，一次性输出所有结构化数据，适用于短视频或对理解时效要求较高的场景

        :return: DirectVideoParsingPipeline实例
        """
        return DirectVideoParsingPipeline( 
            custom_processors=custom_processors,
            slice_schema_path=slice_schema_path,
            video_schema_path=video_schema_path,
            enable_vectorization=enable_vectorization,
            enable_persistence=enable_persistence,
            **kwargs
        )

    @staticmethod
    def get_audio_pipeline(**kwargs) -> AudioParsingPipeline:
        """
        创建音频解析流水线实例

        :return: AudioParsingPipeline实例
        """
        return AudioParsingPipeline(**kwargs)

    @staticmethod
    def get_pipeline_for_asset_type(
        asset_type: int,
        enable_persistence: bool = True,
        **kwargs
    ) -> BasePipeline:
        """
        根据资产类型获取对应的解析流水线（Assets模块通用）

        :param asset_type: 资产类型：1-图片, 2-视频, 3-音频, 4-文本
        :param enable_persistence: 是否开启持久化
        :return: 对应的流水线实例
        """
        if asset_type == 3:  # 音频类型使用专门的音频解析流水线
            return PipelineFactory.get_audio_pipeline(
                enable_persistence=enable_persistence,
                **kwargs
            )
        elif asset_type in [1, 2, 4]:  # 图片/视频/文本使用商品解析流水线，支持多模态理解
            return PipelineFactory.get_product_pipeline(
                enable_persistence=enable_persistence,
                **kwargs
            )
        raise ValueError(f"不支持的资产类型: {asset_type}，支持类型：1-图片, 2-视频, 3-音频, 4-文本")
