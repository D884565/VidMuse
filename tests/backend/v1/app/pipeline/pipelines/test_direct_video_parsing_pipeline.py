import json
from unittest.mock import Mock, patch
import sys
import os

# Add backend to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..', 'backend')))

# Mock the circular imports before importing any backend modules
mock_product_dao = Mock()
mock_pipeline_factory = Mock()
sys.modules['backend.v1.app.product.dao.product_dao'] = Mock()
sys.modules['backend.v1.app.pipeline.factory.pipeline_factory'] = Mock()
sys.modules['backend.v1.app.product.dao.product_dao'].ProductDAO = mock_product_dao
sys.modules['backend.v1.app.pipeline.factory.pipeline_factory'].PipelineFactory = mock_pipeline_factory

# Mock the vector database client and DAO to avoid Qdrant connection issues
mock_vector_client = Mock()
sys.modules['backend.store.vector'] = Mock()
sys.modules['backend.store.vector.qdrant_client'] = Mock()
sys.modules['backend.store.vector.qdrant_client.get_qdrant_client'] = Mock(return_value=mock_vector_client)
sys.modules['backend.store.vector.factory'] = Mock()
sys.modules['backend.store.vector.factory.get_vector_db_client'] = Mock(return_value=mock_vector_client)

# Mock CollectionDAO and VectorizationProcessor to avoid initialization issues
mock_collection_dao = Mock()
sys.modules['backend.store.collection'] = Mock()
sys.modules['backend.store.collection.base'] = Mock()
sys.modules['backend.store.collection.base.CollectionDAO'] = mock_collection_dao
mock_vectorization_processor = Mock()
sys.modules['backend.v1.app.pipeline.processors.video.vectorization_processor'] = Mock()
sys.modules['backend.v1.app.pipeline.processors.video.vectorization_processor.VectorizationProcessor'] = mock_vectorization_processor

# Mock the entire providers module structure
mock_providers = Mock()
mock_providers_dto = Mock()
mock_providers_dto_schema = Mock()
mock_providers_dto_schema.VideoUnderstandingRequest = Mock()
mock_providers.dto = mock_providers_dto
mock_providers.dto.schema = mock_providers_dto_schema
mock_providers.VolcanoLLM = Mock()
sys.modules['backend.providers'] = mock_providers
sys.modules['backend.providers.dto'] = mock_providers_dto
sys.modules['backend.providers.dto.schema'] = mock_providers_dto_schema

# Now import the modules
from backend.v1.app.pipeline.pipelines import DirectVideoParsingPipeline
from backend.v1.app.pipeline.base import constants


def test_direct_video_parsing_pipeline_init():
    """测试流水线初始化"""
    # 默认初始化
    pipeline = DirectVideoParsingPipeline()
    assert len(pipeline.processors) == 6  # 理解 + 2个校验 + 2个向量化 + 落库
    assert pipeline.pipeline_type == "direct_video"

    # 禁用向量化
    pipeline_no_vec = DirectVideoParsingPipeline(enable_vectorization=False)
    assert len(pipeline_no_vec.processors) == 4  # 理解 + 2个校验 + 落库

    # 自定义处理器
    mock_processor = Mock()
    pipeline_custom = DirectVideoParsingPipeline(custom_processors=[mock_processor])
    assert len(pipeline_custom.processors) == 1
    assert pipeline_custom.processors[0] == mock_processor


@patch("backend.v1.app.pipeline.processors.video.direct_video_understanding_processor.VolcanoLLM")
@patch("backend.v1.app.pipeline.processors.common.asset_persist_processor.AssetDAO")
@patch("backend.v1.app.pipeline.processors.common.asset_persist_processor.get_db")
def test_direct_video_parsing_pipeline_run(mock_get_db, mock_asset_dao, mock_llm_class):
    """测试流水线完整运行流程"""
    # Mock数据库
    mock_db = Mock()
    mock_get_db.return_value = iter([mock_db])

    # Mock资产更新
    mock_asset = Mock()
    mock_asset.to_dict.return_value = {"id": 123, "ai_features": {}}
    mock_asset_dao.update_asset.return_value = mock_asset

    # Mock LLM响应
    mock_llm = Mock()
    mock_response = Mock()
    mock_response.content = json.dumps({
        "video": {
            "视频基本信息": {
                "title": "测试视频",
                "duration": 60
            }
        },
        "slices": [
            {
                "creative_elements": {
                    "start_time": 0,
                    "end_time": 10,
                    "script": "测试台词"
                }
            }
        ]
    })
    # Make video_understanding return a coroutine
    async def mock_video_understanding(*args, **kwargs):
        return mock_response
    mock_llm.video_understanding = mock_video_understanding
    mock_llm_class.return_value = mock_llm

    # 创建流水线（禁用向量化，简化测试）
    pipeline = DirectVideoParsingPipeline(enable_vectorization=False, enable_persistence=False)

    # 准备输入数据
    input_data = {
        constants.VIDEO_URL: "https://example.com/test.mp4",
        constants.VIDEO_ID: "test_vid_123",
        "asset_id": 123,
        "video_duration": 60000,
        "user_id": 1
    }

    # 运行流水线
    result = pipeline.run(input_data)

    # 验证结果
    assert result["success"] is True
    assert "data" in result
    assert constants.SLICE_DATA in result["data"]
    assert constants.VIDEO_DATA in result["data"]
    assert constants.AI_FEATURES in result["data"]
    assert "asset_info" in result["data"]

    # 验证落库调用
    mock_asset_dao.update_asset.assert_called_once()
    update_args = mock_asset_dao.update_asset.call_args
    assert update_args[0][0] == mock_db
    assert update_args[0][1] == 123
    assert "ai_features" in update_args[0][2]
    assert update_args[0][2]["parsing_status"] == "completed"
