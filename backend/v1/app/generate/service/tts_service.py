"""TTS 语音合成服务（接入火山引擎 HTTP API）"""
import os
import uuid
import base64
import tempfile
import logging

import requests

from backend.v1.app.config.config import settings

logger = logging.getLogger(__name__)

# 火山引擎 TTS API 配置
TTS_API_URL = "https://openspeech.bytedance.com/api/v1/tts"


class TtsService:
    """语音合成服务（火山引擎 HTTP API）"""

    def __init__(self):
        self.temp_dir = tempfile.gettempdir()
        # TTS_ACCESS_KEY 作为 appid，TTS_SECRET_KEY 作为 access_token
        self.app_id = settings.TTS_ACCESS_KEY
        self.token = settings.TTS_SECRET_KEY

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
            logger.warning(f"[TTS] 火山引擎调用失败，使用静音音频: {str(e)}")
            return self._create_silent_audio(text)

    def _call_volcano_tts(self, text: str, voice_type: str) -> str:
        """
        调用火山引擎 TTS HTTP API。

        :param text: 配音文本
        :param voice_type: 音色
        :returns: 音频文件路径
        """
        # 鉴权头：Bearer;token
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer;{self.token}",
        }

        # 构建请求体
        payload = {
            "app": {
                "appid": self.app_id,
                "token": "fake_token",  # 无实际鉴权作用，可传任意非空字符串
                "cluster": "volcano_tts",
            },
            "user": {
                "uid": "vidmuse_user",
            },
            "audio": {
                "voice_type": voice_type,
                "encoding": "mp3",
                "speed_ratio": 1.0,
                "volume_ratio": 1.0,
            },
            "request": {
                "reqid": uuid.uuid4().hex,
                "text": text,
                "operation": "query",
            },
        }

        # 发送请求
        response = requests.post(TTS_API_URL, json=payload, headers=headers, timeout=30)
        response.raise_for_status()

        # 解析响应
        resp_data = response.json()
        if resp_data.get("code") != 3000:
            raise Exception(f"TTS API 返回错误: {resp_data.get('message', '未知错误')}")

        # 提取音频数据（Base64 编码）
        audio_base64 = resp_data.get("data", "")
        if not audio_base64:
            raise Exception("TTS API 返回空音频数据")

        # 解码并保存音频文件
        audio_bytes = base64.b64decode(audio_base64)
        output_path = os.path.join(self.temp_dir, f"tts_{uuid.uuid4().hex}.mp3")
        with open(output_path, "wb") as f:
            f.write(audio_bytes)

        logger.info(f"[TTS] 火山引擎调用成功: {output_path}, 大小: {len(audio_bytes)} bytes")
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
            import subprocess
            cmd = [
                "ffmpeg",
                "-y",
                "-f", "lavfi",
                "-i", "anullsrc=r=44100:cl=mono",
                "-t", str(duration_sec),
                "-q:a", "9",
                "-acodec", "libmp3lame",
                output_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                raise RuntimeError(f"create silent mp3 failed: {result.stderr}")

        return output_path


tts_service = TtsService()
