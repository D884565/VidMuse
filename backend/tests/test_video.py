"""视频处理模块测试"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from backend.v1.app.video.service.video_service import VideoService


@pytest.fixture
def video_service():
    """创建视频服务实例"""
    return VideoService()


@pytest.fixture
def mock_db():
    """模拟数据库会话"""
    return AsyncMock()


@pytest.fixture
def mock_asset():
    """模拟视频资产"""
    asset = MagicMock()
    asset.id = 1
    asset.url = "/path/to/video.mp4"
    asset.type = "video"
    return asset


@pytest.mark.asyncio
async def test_get_video_info_success(video_service, mock_db, mock_asset):
    """测试成功获取视频信息"""
    # 模拟数据库查询
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_asset
    mock_db.execute.return_value = mock_result

    # 模拟 FFmpeg 工具
    with patch("backend.v1.app.video.service.video_service.ffmpeg_utils") as mock_ffmpeg:
        mock_ffmpeg.get_video_info.return_value = {
            "duration": 10.0,
            "width": 1920,
            "height": 1080,
            "format": "mp4",
            "file_size": 1024000,
            "fps": 30.0,
        }

        # 模拟文件存在
        with patch("os.path.exists", return_value=True):
            result = await video_service.get_video_info(mock_db, 1)

    assert result["video_id"] == 1
    assert result["duration"] == 10.0
    assert result["width"] == 1920
    assert result["height"] == 1080


@pytest.mark.asyncio
async def test_get_video_info_not_found(video_service, mock_db):
    """测试视频不存在"""
    # 模拟数据库查询返回空
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    with pytest.raises(ValueError, match="视频不存在"):
        await video_service.get_video_info(mock_db, 999)


@pytest.mark.asyncio
async def test_get_video_info_file_not_found(video_service, mock_db, mock_asset):
    """测试视频文件不存在"""
    # 模拟数据库查询
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_asset
    mock_db.execute.return_value = mock_result

    # 模拟文件不存在
    with patch("os.path.exists", return_value=False):
        with pytest.raises(ValueError, match="视频文件不存在"):
            await video_service.get_video_info(mock_db, 1)


@pytest.mark.asyncio
async def test_split_video_success(video_service, mock_db, mock_asset):
    """测试成功分段视频"""
    # 模拟数据库查询
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_asset
    mock_db.execute.return_value = mock_result

    # 模拟 FFmpeg 工具
    with patch("backend.v1.app.video.service.video_service.ffmpeg_utils") as mock_ffmpeg:
        mock_ffmpeg.get_video_info.return_value = {
            "duration": 10.0,
            "width": 1920,
            "height": 1080,
            "format": "mp4",
            "file_size": 1024000,
            "fps": 30.0,
        }
        mock_ffmpeg.split_video.return_value = "/path/to/segment.mp4"

        # 模拟文件存在和目录创建
        with patch("os.path.exists", return_value=True), \
             patch("os.makedirs"):
            result = await video_service.split_video(mock_db, 1, [3.0, 6.0, 9.0])

    assert result["video_id"] == 1
    assert result["duration"] == 10.0
    assert result["total_segments"] == 4


@pytest.mark.asyncio
async def test_split_video_timestamps_exceed_duration(video_service, mock_db, mock_asset):
    """测试时间戳超出视频时长"""
    # 模拟数据库查询
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_asset
    mock_db.execute.return_value = mock_result

    # 模拟 FFmpeg 工具
    with patch("backend.v1.app.video.service.video_service.ffmpeg_utils") as mock_ffmpeg:
        mock_ffmpeg.get_video_info.return_value = {
            "duration": 10.0,
            "width": 1920,
            "height": 1080,
            "format": "mp4",
            "file_size": 1024000,
            "fps": 30.0,
        }

        # 模拟文件存在
        with patch("os.path.exists", return_value=True):
            with pytest.raises(ValueError, match="时间戳超出视频时长"):
                await video_service.split_video(mock_db, 1, [15.0])
