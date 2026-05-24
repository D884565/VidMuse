"""TTS 语音合成服务（接入火山引擎）"""
import os
import uuid
import tempfile
import logging

from backend.v1.app.config.config import settings

logger = logging.getLogger(__name__)


class TtsService:
    """语音合成服务（火山引擎）"""

    def __init__(self):
        self.temp_dir = tempfile.gettempdir()
        self.access_key = settings.TTS_ACCESS_KEY
        self.secret_key = settings.TTS_SECRET_KEY

    def generate_audio(self, text: str, voice_type: str = "zh_female_cancan_mars_bigtts") -> str:
        """
        将文本合成为配音音频。

        :param text: 配音文本
        :param voice_type: 音色
        :returns: 本地音频文件路径
        """
        try:
            return self._call_volcano_tts(text, voice_type)
        except Exception as e:
            logger.warning(f"[TTS] 火山引擎调用失败，使用 Mock: {str(e)}")
            return self._create_silent_audio(text)

    def _call_volcano_tts(self, text: str, voice_type: str) -> str:
        """
        调用火山引擎 TTS API。

        :param text: 配音文本
        :param voice_type: 音色
        :returns: 音频文件路径
        """
        from volcengine.tts import TtsService as VolcTtsService

        # 初始化 TTS 服务
        tts_service = VolcTtsService()
        tts_service.set_ak(self.access_key)
        tts_service.set_sk(self.secret_key)

        # 调用语音合成
        resp = tts_service.synthesize(
            text=text,
            voice_type=voice_type,
            encoding="mp3",
            speed_ratio=1.0,
            volume_ratio=1.0,
            pitch_ratio=1.0,
        )

        # 保存音频文件
        output_path = os.path.join(self.temp_dir, f"tts_{uuid.uuid4().hex}.mp3")
        with open(output_path, "wb") as f:
            f.write(resp.audio_data)

        logger.info(f"[TTS] 火山引擎调用成功: {output_path}")
        return output_path

    def _create_silent_audio(self, text: str) -> str:
        """创建静音音频（作为 fallback）"""
        output_path = os.path.join(self.temp_dir, f"tts_{uuid.uuid4().hex}.mp3")
        duration_sec = max(1, len(text) // 4)

        try:
            from moviepy import AudioClip
            # 创建静音音频
            clip = AudioClip(lambda t: 0, duration=duration_sec, fps=44100)
            clip.write_audiofile(output_path, logger=None)
            clip.close()
        except Exception:
            # 如果 moviepy 失败，创建一个空文件
            with open(output_path, "wb") as f:
                f.write(b"\x00" * 1024)

        return output_path


tts_service = TtsService()
