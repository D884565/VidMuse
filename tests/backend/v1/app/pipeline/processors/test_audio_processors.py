import pytest
from unittest.mock import Mock, patch
from backend.v1.app.pipeline.processors.audio_info_extract_processor import AudioInfoExtractProcessor
from backend.v1.app.pipeline.processors.audio_asr_processor import AudioASRProcessor
from backend.v1.app.pipeline.processors.audio_classification_processor import AudioClassificationProcessor
from backend.v1.app.pipeline.processors.audio_result_aggregator import AudioResultAggregator
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

def test_audio_asr_processor_with_mock_config():
    # 测试配置缺失时返回模拟数据
    with patch('backend.v1.app.pipeline.processors.audio_asr_processor.settings',
               VOLC_ENGINE_ACCESS_KEY=None,
               VOLC_ENGINE_SECRET_KEY=None):
        context = PipelineContext({
            "audio_url": "https://test.com/test.mp3",
            "object_name": "test/audio/test.mp3",
            "duration": 10.5
        })

        processor = AudioASRProcessor()
        result = processor.process(context)

        assert "transcript" in result.data
        assert "language" in result.data
        assert "speakers" in result.data
        assert isinstance(result.data["transcript"], str)
        assert isinstance(result.data["speakers"], list)
        assert result.data["transcript"] == "语音识别功能未配置，使用模拟识别结果"
        assert result.data["language"] == "zh-CN"
        assert result.data["speakers"] == ["说话人1"]

def test_audio_asr_processor_missing_audio_params():
    # 测试缺少音频参数的情况
    with patch('backend.v1.app.pipeline.processors.audio_asr_processor.settings',
               VOLC_ENGINE_ACCESS_KEY="test_key",
               VOLC_ENGINE_SECRET_KEY="test_secret",
               VOLC_ENGINE_ASR_ENDPOINT="https://asr.test.com",
               VOLC_ENGINE_ASR_APP_ID="test_app_id"):
        context = PipelineContext({
            "duration": 10.5
        })

        processor = AudioASRProcessor()
        result = processor.process(context)

        assert result.data["transcript"] == "未找到音频文件"
        assert result.data["language"] == "unknown"
        assert result.data["speakers"] == []

def test_audio_asr_processor_api_success():
    # 测试API调用成功的情况
    mock_response = Mock()
    mock_response.json.return_value = {
        "code": 0,
        "result": {
            "text": "这是测试语音识别结果",
            "language": "zh-CN",
            "speaker_info": [
                {"speaker_id": 0, "start_time": 0, "end_time": 2},
                {"speaker_id": 1, "start_time": 2, "end_time": 5}
            ]
        }
    }
    mock_response.raise_for_status.return_value = None

    with patch('backend.v1.app.pipeline.processors.audio_asr_processor.requests.post', return_value=mock_response):
        with patch('backend.v1.app.pipeline.processors.audio_asr_processor.settings',
                   VOLC_ENGINE_ACCESS_KEY="test_key",
                   VOLC_ENGINE_SECRET_KEY="test_secret",
                   VOLC_ENGINE_ASR_ENDPOINT="https://asr.test.com",
                   VOLC_ENGINE_ASR_APP_ID="test_app_id"):
            context = PipelineContext({
                "audio_url": "https://test.com/test.mp3",
                "duration": 10.5
            })

            processor = AudioASRProcessor()
            result = processor.process(context)

            assert result.data["transcript"] == "这是测试语音识别结果"
            assert result.data["language"] == "zh-CN"
            assert result.data["speakers"] == ["说话人0", "说话人1"]

def test_audio_classification_processor_with_mock_config():
    # 测试配置缺失时返回模拟数据
    with patch('backend.v1.app.pipeline.processors.audio_classification_processor.settings',
               VOLC_ENGINE_ACCESS_KEY=None,
               VOLC_ENGINE_SECRET_KEY=None):
        context = PipelineContext({
            "audio_url": "https://test.com/test.mp3",
            "object_name": "test/audio/test.mp3",
            "transcript": "这是一段访谈内容"
        })

        processor = AudioClassificationProcessor()
        result = processor.process(context)

        assert "audio_type" in result.data
        assert "has_background_music" in result.data
        assert "background_music_genre" in result.data
        assert "objects" in result.data
        assert isinstance(result.data["objects"], list)
        assert result.data["audio_type"] == "未知"
        assert result.data["has_background_music"] == False
        assert result.data["background_music_genre"] == "未知"
        assert result.data["objects"] == ["音频"]

def test_audio_classification_processor_api_success():
    # 测试API调用成功的情况
    mock_response = Mock()
    mock_response.json.return_value = {
        "code": 0,
        "result": {
            "audio_type": "访谈",
            "music_detection": {
                "has_music": True,
                "genre": "流行"
            },
            "sound_effects": ["笑声", "掌声"]
        }
    }
    mock_response.raise_for_status.return_value = None

    with patch('backend.v1.app.pipeline.processors.audio_classification_processor.requests.post', return_value=mock_response):
        with patch('backend.v1.app.pipeline.processors.audio_classification_processor.settings',
                   VOLC_ENGINE_ACCESS_KEY="test_key",
                   VOLC_ENGINE_SECRET_KEY="test_secret",
                   VOLC_ENGINE_AUDIO_CLASSIFICATION_ENDPOINT="https://audio-classify.test.com"):
            context = PipelineContext({
                "audio_url": "https://test.com/test.mp3",
                "transcript": "这是一段访谈内容"
            })

            processor = AudioClassificationProcessor()
            result = processor.process(context)

            assert result.data["audio_type"] == "访谈"
            assert result.data["has_background_music"] == True
            assert result.data["background_music_genre"] == "流行"
            assert set(result.data["objects"]) == {"访谈", "背景音乐", "笑声", "掌声"}

def test_audio_result_aggregator():
    context = PipelineContext({
        "duration": 125.5,
        "sample_rate": 44100,
        "channels": 2,
        "bitrate": 192000,
        "transcript": "这是一段访谈内容，包含背景音乐",
        "language": "zh-CN",
        "speakers": ["说话人1", "说话人2"],
        "audio_type": "访谈",
        "has_background_music": True,
        "background_music_genre": "轻快",
        "objects": ["访谈", "背景音乐", "对话"]
    })

    processor = AudioResultAggregator()
    result = processor.process(context)

    assert "slice_len" in result.data
    assert "scene" in result.data
    assert "mood" in result.data
    assert "ai_features" in result.data
    assert result.data["slice_len"] == 1
    assert isinstance(result.data["ai_features"], dict)
    assert result.data["ai_features"]["duration"] == 125.5
    assert result.data["ai_features"]["transcript"] == "这是一段访谈内容，包含背景音乐"

