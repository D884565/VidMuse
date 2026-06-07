import json
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

# 先解决循环导入问题，在导入pipeline模块前先导入product相关模块
# 先导入product模块，避免循环
from backend.v1.app.product.dao.product_dao import ProductDAO
from backend.v1.app.product.service.product_service import ProductService

# 现在可以正常导入了
from unittest.mock import Mock, patch, AsyncMock
from backend.v1.app.pipeline.base import PipelineContext, constants
from backend.v1.app.pipeline.utils import prompt_manager

# 添加缺失的常量
constants.VIDEO_URL = "video_url"

# Mock prompt_manager的方法（匹配新的签名）
def mock_get_direct_prompt(video_url, video_duration=0):
    return f"""请分析视频内容，输出JSON。
视频URL: {video_url}
视频时长: {video_duration}秒

请输出包含video和slices字段的JSON。"""

prompt_manager.get_direct_video_understanding_prompt = mock_get_direct_prompt

from backend.v1.app.pipeline.processors.video import DirectVideoUnderstandingProcessor


import asyncio

def test_direct_video_understanding_processor_success():
    """测试直接视频理解处理器成功场景"""
    # Mock LLM客户端
    mock_llm = Mock()
    mock_response = Mock()
    mock_response.content = json.dumps({
        "video": {
            "视频基本信息": {
                "title": "测试视频",
                "duration": 60,
                "category": "测试分类"
            },
            "片段间关系": {
                "逻辑关系": "顺序",
                "主题一致性": "高"
            }
        },
        "slices": [
            {
                "creative_elements": {
                    "start_time": 0,
                    "end_time": 10,
                    "script": "测试台词1"
                },
                "content_summary": "片段1内容"
            },
            {
                "creative_elements": {
                    "start_time": 10,
                    "end_time": 20,
                    "script": "测试台词2"
                },
                "content_summary": "片段2内容"
            }
        ]
    })
    # 使用AsyncMock来模拟异步方法
    mock_llm.video_understanding = AsyncMock(return_value=mock_response)

    # 创建处理器
    processor = DirectVideoUnderstandingProcessor(llm_client=mock_llm)

    # 准备上下文
    context = PipelineContext({
        constants.VIDEO_URL: "https://example.com/test.mp4",
        constants.VIDEO_ID: "test_vid_123",
        "asset_id": 123,
        "video_duration": 60000
    })

    # 执行处理
    result_context = processor.process(context)

    # 验证结果
    assert not result_context.has_errors()

    # 验证slice_data
    slice_data = result_context.get(constants.SLICE_DATA)
    assert len(slice_data) == 2
    assert slice_data[0]["slice_id"] == "test_vid_123_slice_0"
    assert slice_data[0]["video_id"] == "test_vid_123"
    assert slice_data[0]["slice_index"] == 0

    # 验证video_data
    video_data = result_context.get(constants.VIDEO_DATA)
    assert video_data["video_id"] == "test_vid_123"
    assert video_data["video_duration"] == 60000
    assert video_data["asset_id"] == 123
    assert "视频基本信息" in video_data

    # 验证embed_slices
    embed_slices = result_context.get(constants.EMBED_SLICES)
    assert len(embed_slices) == 2
    assert embed_slices[0]["slice_id"] == "test_vid_123_slice_0"
    assert "content" in embed_slices[0]

    # 验证embed_video
    embed_video = result_context.get(constants.EMBED_VIDEO)
    assert embed_video["video_id"] == "test_vid_123"
    assert "content" in embed_video

    # 验证ai_features
    ai_features = result_context.get(constants.AI_FEATURES)
    assert ai_features["video_info"]["video_id"] == "test_vid_123"
    assert len(ai_features["slices"]) == 2
    assert ai_features["parse_type"] == "direct_video"

    # 验证LLM调用参数
    mock_llm.video_understanding.assert_called_once()
    call_args = mock_llm.video_understanding.call_args[0][0]
    assert call_args.video_url == "https://example.com/test.mp4"


def test_direct_video_understanding_processor_missing_params():
    """测试缺少必要参数的情况"""
    processor = DirectVideoUnderstandingProcessor()

    # 缺少video_url
    context = PipelineContext({
        constants.VIDEO_ID: "test_vid_123",
        "asset_id": 123
    })
    try:
        result_context = processor.process(context)
        assert False, "Expected ValueError but none was raised"
    except ValueError as e:
        assert "video_url is required" in str(e)


def test_direct_video_understanding_processor_json_parse_error():
    """测试JSON解析失败场景"""
    mock_llm = Mock()
    mock_response = Mock()
    mock_response.content = "invalid json"
    # 使用AsyncMock来模拟异步方法
    mock_llm.video_understanding = AsyncMock(return_value=mock_response)

    processor = DirectVideoUnderstandingProcessor(llm_client=mock_llm)

    context = PipelineContext({
        constants.VIDEO_URL: "https://example.com/test.mp4",
        constants.VIDEO_ID: "test_vid_123",
        "asset_id": 123
    })

    result_context = processor.process(context)
    assert result_context.has_errors()
    assert "parse failed" in str(result_context.get_errors()[0])


def test_direct_video_understanding_processor_video_url_compatibility():
    """测试video_url参数兼容性，支持video_url和video_file两种键名"""
    # Mock LLM客户端
    mock_llm = Mock()
    mock_response = Mock()
    mock_response.content = json.dumps({
        "video": {
            "视频基本信息": {
                "title": "测试视频",
                "duration": 60
            }
        },
        "slices": []
    })
    # 使用AsyncMock来模拟异步方法
    mock_llm.video_understanding = AsyncMock(return_value=mock_response)

    processor = DirectVideoUnderstandingProcessor(llm_client=mock_llm)

    # 测试1：使用video_url键
    context1 = PipelineContext({
        "video_url": "https://example.com/test1.mp4",
        constants.VIDEO_ID: "test_vid_123",
        "asset_id": 123
    })
    result1 = processor.process(context1)
    assert not result1.has_errors()
    assert result1.get(constants.VIDEO_DATA)["video_id"] == "test_vid_123"

    # 测试2：使用video_file键（即constants.VIDEO_URL在实际代码中的值）
    context2 = PipelineContext({
        "video_file": "https://example.com/test2.mp4",
        constants.VIDEO_ID: "test_vid_456",
        "asset_id": 456
    })
    result2 = processor.process(context2)
    assert not result2.has_errors()
    assert result2.get(constants.VIDEO_DATA)["video_id"] == "test_vid_456"
