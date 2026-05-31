import sys
import pytest
from unittest.mock import Mock, patch

# 先mock整个search模块，避免导入时初始化错误
sys.modules['backend.v1.app.search'] = Mock()
sys.modules['backend.v1.app.search.core'] = Mock()
sys.modules['backend.v1.app.search.core.component_registry'] = Mock()
sys.modules['backend.v1.app.search.agent'] = Mock()
sys.modules['backend.v1.app.search.agent.service'] = Mock()

from fastapi import UploadFile
from sqlalchemy.orm import Session
from backend.v1.app.assets.service.asset_service import AssetService
from backend.v1.app.pipeline import AudioParsingPipeline

@pytest.mark.asyncio
async def test_upload_audio_asset():
    """测试上传音频资产并解析"""
    # 模拟db会话和上传文件
    db_session = Mock(spec=Session)
    mock_file = Mock(spec=UploadFile)
    mock_file.filename = "test.mp3"
    mock_file.content_type = "audio/mpeg"
    mock_file.size = 1024 * 1024
    mock_file.file = Mock()

    # Mock文件验证和上传
    with patch.object(AssetService, '_validate_file', return_value='mp3'):
        with patch.object(AssetService, 'generate_object_name', return_value='assets/audio/test/test.mp3'):
            with patch('backend.v1.app.assets.service.asset_service.get_storage_client') as mock_storage:
                mock_client = Mock()
                mock_client.upload_fileobj.return_value = "https://test.com/assets/audio/test/test.mp3"
                mock_storage.return_value = mock_client

                # Mock资产创建
                mock_created_asset = Mock()
                mock_created_asset.id = 1
                mock_created_asset.type = 3
                mock_created_asset.url = "https://test.com/assets/audio/test/test.mp3"
                mock_created_asset.ai_features = {
                    "scene": "访谈音频",
                    "mood": "正式",
                    "objects": ["访谈", "对话"],
                    "duration": 125.5,
                    "sample_rate": 44100,
                    "transcript": "测试语音内容"
                }
                mock_created_asset.parsing_status = "completed"
                mock_created_asset.execution_id = "test_execution_id"
                mock_created_asset.duration = 125.5
                mock_created_asset.title = "测试音频"
                mock_created_asset.to_dict.return_value = {
                    "id": 1,
                    "type": 3,
                    "title": "测试音频",
                    "url": "https://test.com/assets/audio/test/test.mp3",
                    "duration": 125.5,
                    "file_size": 1024 * 1024,
                    "format": "mp3",
                    "source_type": 0,
                    "created_at": "2026-05-31T12:00:00Z",
                    "ai_features": {
                        "scene": "访谈音频",
                        "mood": "正式",
                        "objects": ["访谈", "对话"],
                        "duration": 125.5,
                        "sample_rate": 44100,
                        "transcript": "测试语音内容"
                    },
                    "parsing_status": "completed",
                    "execution_id": "test_execution_id",
                    "parsing_error": None
                }

                with patch('backend.v1.app.assets.dao.AssetDAO.create_asset', return_value=mock_created_asset):
                    with patch.object(AssetService, '_process_asset_parsing') as mock_process:
                        mock_process.return_value = {
                            "duration": 125.5,
                            "ai_features": {
                                "scene": "访谈音频",
                                "mood": "正式",
                                "objects": ["访谈", "对话"],
                                "duration": 125.5,
                                "sample_rate": 44100,
                                "transcript": "测试语音内容"
                            }
                        }
                        # 调用上传方法
                        result = await AssetService.upload_user_asset(
                            db=db_session,
                            background_tasks=Mock(),
                            file=mock_file,
                            type=3,  # 音频类型
                            title="测试音频",
                            source_type=0,
                            skip_analysis=False
                        )

                        # 验证结果
                        assert result["type"] == 3
                        assert result["type_name"] == "音频"
                        assert result["ai_features"] is not None
                        assert result["ai_features"]["duration"] == 125.5
                        assert result["ai_features"]["transcript"] == "测试语音内容"
                        assert result["analysis_performed"] == True

@pytest.mark.asyncio
async def test_parse_audio_asset():
    """测试手动触发音频解析"""
    # 模拟db会话和资产数据
    db_session = Mock(spec=Session)
    mock_asset = Mock()
    mock_asset.id = 1
    mock_asset.type = 3
    mock_asset.url = "https://test.com/test.mp3"
    mock_asset.ai_features = None
    mock_asset.parsing_status = "pending"
    # 先返回初始状态
    initial_asset_dict = {
        "id": 1,
        "type": 3,
        "title": "测试音频",
        "url": "https://test.com/test.mp3",
        "duration": None,
        "ai_features": None,
        "parsing_status": "pending",
        "execution_id": None,
        "parsing_error": None
    }
    # 处理后返回更新状态
    updated_asset_dict = {
        "id": 1,
        "type": 3,
        "title": "测试音频",
        "url": "https://test.com/test.mp3",
        "duration": 200.0,
        "ai_features": {
            "scene": "音乐音频",
            "mood": "愉悦",
            "objects": ["音乐"],
            "duration": 200.0,
            "audio_type": "音乐"
        },
        "parsing_status": "completed",
        "execution_id": "test_exec_id",
        "parsing_error": None
    }
    mock_asset.to_dict.side_effect = [initial_asset_dict, updated_asset_dict]

    # Mock get_asset_by_id在第二次调用时返回更新后的资产
    def mock_get_asset_by_id(db, asset_id):
        if not hasattr(mock_get_asset_by_id, 'call_count'):
            mock_get_asset_by_id.call_count = 0
        mock_get_asset_by_id.call_count += 1
        if mock_get_asset_by_id.call_count == 1:
            return mock_asset
        else:
            # 返回更新后的资产
            updated_asset = Mock()
            updated_asset.to_dict.return_value = updated_asset_dict
            return updated_asset

    with patch('backend.v1.app.assets.dao.AssetDAO.get_asset_by_id', side_effect=mock_get_asset_by_id):
        with patch('backend.v1.app.assets.dao.AssetDAO.update_asset') as mock_update:
            with patch.object(AssetService, '_process_asset_parsing') as mock_process:
                mock_process.return_value = Mock()
                # 调用解析方法
                result = await AssetService.parse_asset(db=db_session, asset_id=1, force=False)

                # 验证结果
                assert result["parsing_status"] == "completed"
                assert result["ai_features"]["audio_type"] == "音乐"
                assert result["analysis_completed"] == True
