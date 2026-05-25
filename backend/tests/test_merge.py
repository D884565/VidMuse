"""音视频合成模块测试"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from backend.v1.app.merge.service.merge_service import MergeService


@pytest.fixture
def merge_service():
    """创建合成服务实例"""
    return MergeService()


@pytest.fixture
def mock_db():
    """模拟数据库会话"""
    return AsyncMock()


@pytest.fixture
def mock_video_asset():
    """模拟视频资产"""
    asset = MagicMock()
    asset.id = 1
    asset.url = "/path/to/video.mp4"
    asset.type = "video"
    return asset


@pytest.fixture
def mock_audio_asset():
    """模拟音频资产"""
    asset = MagicMock()
    asset.id = 2
    asset.url = "/path/to/audio.mp3"
    asset.type = "audio"
    return asset


@pytest.mark.asyncio
async def test_replace_audio_success(merge_service, mock_db, mock_video_asset, mock_audio_asset):
    """测试成功替换音频"""
    # 模拟数据库查询
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.side_effect = [mock_video_asset, mock_audio_asset]
    mock_db.execute.return_value = mock_result

    # 模拟 FFmpeg 工具
    with patch("backend.v1.app.merge.service.merge_service.ffmpeg_utils") as mock_ffmpeg:
        mock_ffmpeg.replace_audio.return_value = "/path/to/output.mp4"

        # 模拟文件存在和目录创建
        with patch("os.path.exists", return_value=True), \
             patch("os.makedirs"):
            result = await merge_service.replace_audio(mock_db, 1, 2)

    assert result["video_id"] == 1
    assert result["audio_id"] == 2
    assert result["status"] == "queued"


@pytest.mark.asyncio
async def test_replace_audio_video_not_found(merge_service, mock_db):
    """测试视频不存在"""
    # 模拟数据库查询返回空
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    with pytest.raises(ValueError, match="资产不存在"):
        await merge_service.replace_audio(mock_db, 999, 2)


@pytest.mark.asyncio
async def test_replace_audio_audio_not_found(merge_service, mock_db, mock_video_asset):
    """测试音频不存在"""
    # 模拟数据库查询
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.side_effect = [mock_video_asset, None]
    mock_db.execute.return_value = mock_result

    with patch("os.path.exists", return_value=True):
        with pytest.raises(ValueError, match="资产不存在"):
            await merge_service.replace_audio(mock_db, 1, 999)


@pytest.mark.asyncio
async def test_add_bgm_success(merge_service, mock_db, mock_video_asset, mock_audio_asset):
    """测试成功添加BGM"""
    # 模拟数据库查询
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.side_effect = [mock_video_asset, mock_audio_asset]
    mock_db.execute.return_value = mock_result

    # 模拟 FFmpeg 工具
    with patch("backend.v1.app.merge.service.merge_service.ffmpeg_utils") as mock_ffmpeg:
        mock_ffmpeg.add_bgm.return_value = "/path/to/output.mp4"

        # 模拟文件存在和目录创建
        with patch("os.path.exists", return_value=True), \
             patch("os.makedirs"):
            result = await merge_service.add_bgm(mock_db, 1, 2, 0.3, 1.0)

    assert result["video_id"] == 1
    assert result["bgm_id"] == 2
    assert result["status"] == "queued"


@pytest.mark.asyncio
async def test_mix_audio_tracks_success(merge_service, mock_db, mock_video_asset, mock_audio_asset):
    """测试成功混合多音轨"""
    # 模拟数据库查询
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.side_effect = [mock_video_asset, mock_audio_asset, mock_audio_asset]
    mock_db.execute.return_value = mock_result

    # 模拟 FFmpeg 工具
    with patch("backend.v1.app.merge.service.merge_service.ffmpeg_utils") as mock_ffmpeg:
        mock_ffmpeg.mix_audio_tracks.return_value = "/path/to/output.mp4"

        # 模拟文件存在和目录创建
        with patch("os.path.exists", return_value=True), \
             patch("os.makedirs"):
            result = await merge_service.mix_audio_tracks(mock_db, 1, [2, 3], [0.5, 0.5])

    assert result["video_id"] == 1
    assert result["audio_ids"] == [2, 3]
    assert result["status"] == "queued"


@pytest.mark.asyncio
async def test_get_task_status_success(merge_service, mock_db):
    """测试成功获取任务状态"""
    # 模拟数据库查询
    mock_task = MagicMock()
    mock_task.task_id = "merge_123"
    mock_task.task_type = "audio_replace"
    mock_task.video_id = 1
    mock_task.status = "completed"
    mock_task.result = '{"output_path": "/path/to/output.mp4"}'
    mock_task.error_message = None
    mock_task.created_at = MagicMock()
    mock_task.created_at.isoformat.return_value = "2026-05-25T10:00:00"
    mock_task.updated_at = MagicMock()
    mock_task.updated_at.isoformat.return_value = "2026-05-25T10:01:00"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_task
    mock_db.execute.return_value = mock_result

    result = await merge_service.get_task_status(mock_db, "merge_123")

    assert result["task_id"] == "merge_123"
    assert result["status"] == "completed"
    assert result["result"]["output_path"] == "/path/to/output.mp4"


@pytest.mark.asyncio
async def test_get_task_status_not_found(merge_service, mock_db):
    """测试任务不存在"""
    # 模拟数据库查询返回空
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    with pytest.raises(ValueError, match="任务不存在"):
        await merge_service.get_task_status(mock_db, "merge_999")


@pytest.mark.asyncio
async def test_cancel_task_success(merge_service, mock_db):
    """测试成功取消任务"""
    # 模拟数据库查询
    mock_task = MagicMock()
    mock_task.task_id = "merge_123"
    mock_task.status = "queued"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_task
    mock_db.execute.return_value = mock_result

    result = await merge_service.cancel_task(mock_db, "merge_123")

    assert result["task_id"] == "merge_123"
    assert result["status"] == "cancelled"


@pytest.mark.asyncio
async def test_cancel_task_not_found(merge_service, mock_db):
    """测试取消不存在的任务"""
    # 模拟数据库查询返回空
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    with pytest.raises(ValueError, match="任务不存在"):
        await merge_service.cancel_task(mock_db, "merge_999")


@pytest.mark.asyncio
async def test_cancel_task_invalid_status(merge_service, mock_db):
    """测试取消状态不允许的任务"""
    # 模拟数据库查询
    mock_task = MagicMock()
    mock_task.task_id = "merge_123"
    mock_task.status = "completed"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_task
    mock_db.execute.return_value = mock_result

    with pytest.raises(ValueError, match="任务状态不允许取消"):
        await merge_service.cancel_task(mock_db, "merge_123")
