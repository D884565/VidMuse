"""TTS 语音合成服务"""
import os
import uuid
import tempfile


class TtsService:
    """语音合成服务（当前返回 Mock 音频）"""

    def __init__(self):
        self.temp_dir = tempfile.gettempdir()

    def generate_audio(self, text: str, voice_type: str = "zh-CN-XiaoxiaoNeural") -> str:
        """
        将文本合成为配音音频。

        :param text: 配音文本
        :param voice_type: 音色
        :returns: 本地音频文件路径（后续由调用方上传 MinIO）
        """
        # Mock：生成一个空音频文件（后续接入真实 TTS API）
        output_path = os.path.join(self.temp_dir, f"tts_{uuid.uuid4().hex}.mp3")
        self._create_silent_audio(output_path, duration_sec=len(text) // 4)
        return output_path

    def _create_silent_audio(self, path: str, duration_sec: int):
        """创建一个静音 MP3 占位文件（后续替换为真实 TTS）"""
        import struct
        # 生成一个极简 WAV 文件头 + 静音数据
        sample_rate = 24000
        num_samples = sample_rate * duration_sec
        with open(path, "wb") as f:
            f.write(b"RIFF")
            f.write(struct.pack("<I", 36 + num_samples * 2))
            f.write(b"WAVEfmt ")
            f.write(struct.pack("<I", 16))           # chunk size
            f.write(struct.pack("<H", 1))             # PCM
            f.write(struct.pack("<H", 1))             # mono
            f.write(struct.pack("<I", sample_rate))
            f.write(struct.pack("<I", sample_rate * 2))
            f.write(struct.pack("<H", 2))             # block align
            f.write(struct.pack("<H", 16))            # bits per sample
            f.write(b"data")
            f.write(struct.pack("<I", num_samples * 2))
            f.write(b"\x00\x00" * num_samples)


tts_service = TtsService()
