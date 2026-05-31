import pytest
from unittest.mock import Mock, patch
from backend.v1.app.pipeline.processors.audio_info_extract_processor import AudioInfoExtractProcessor
from backend.v1.app.pipeline.base.context import PipelineContext
from pydub import AudioSegment
import io

def test_audio_info_extract_processor_with_object_name():
    # 模拟存储客户端
    mock_client = Mock()
    # 创建一个模拟的音频文件内容
    mock_audio = AudioSegment.silent(duration=1000, frame_rate=44100)
    buffer = io.BytesIO()
    mock_audio.export(buffer, format="wav")
    buffer.seek(0)
    mock_client.download_fileobj.return_value = buffer.read()

    with patch('backend.v1.app.pipeline.processors.audio_info_extract_processor.get_storage_client', return_value=mock_client):
        context = PipelineContext({
            "object_name": "test/audio/test.wav"
        })

        processor = AudioInfoExtractProcessor()
        result = processor.process(context)

        assert not result.has_errors()
        assert "duration" in result.data
        assert "sample_rate" in result.data
        assert "channels" in result.data
        assert "bitrate" in result.data
        assert result.data["duration"] == 1.0
        assert result.data["sample_rate"] == 44100
        assert result.data["channels"] == 1
        assert result.data["bitrate"] > 0

def test_audio_info_extract_processor_with_audio_url():
    # 模拟requests.get返回
    mock_response = Mock()
    mock_audio = AudioSegment.silent(duration=2000, frame_rate=48000).set_channels(2)
    buffer = io.BytesIO()
    mock_audio.export(buffer, format="mp3")
    buffer.seek(0)
    mock_response.content = buffer.read()
    mock_response.raise_for_status.return_value = None

    with patch('backend.v1.app.pipeline.processors.audio_info_extract_processor.requests.get', return_value=mock_response):
        context = PipelineContext({
            "audio_url": "https://test.com/test.mp3"
        })

        processor = AudioInfoExtractProcessor()
        result = processor.process(context)

        assert not result.has_errors()
        assert result.data["duration"] == 2.0
        assert result.data["sample_rate"] == 48000
        assert result.data["channels"] == 2

def test_audio_info_extract_processor_missing_both_params():
    context = PipelineContext({})
    processor = AudioInfoExtractProcessor()
    result = processor.process(context)

    assert result.has_errors()
    assert len(result.errors) == 1
    assert "audio_url or object_name is required" in str(result.errors[0])

def test_audio_info_extract_processor_download_error():
    # 模拟下载失败
    mock_client = Mock()
    mock_client.download_fileobj.side_effect = Exception("Download failed")

    with patch('backend.v1.app.pipeline.processors.audio_info_extract_processor.get_storage_client', return_value=mock_client):
        context = PipelineContext({
            "object_name": "test/audio/test.wav"
        })

        processor = AudioInfoExtractProcessor()
        result = processor.process(context)

        assert result.has_errors()
        assert "Download failed" in str(result.errors[0])
