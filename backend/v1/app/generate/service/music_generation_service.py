"""Suno API 音乐生成服务"""
import logging
import os
import tempfile
import time

import requests

from backend.v1.app.config.config import settings

logger = logging.getLogger(__name__)

SUNO_BASE_URL = "https://api.sunoapi.org/api/v1"
POLL_INTERVAL = 15  # 轮询间隔（秒）
MAX_WAIT_TIME = 180  # 最大等待时间（秒）


class MusicGenerationService:
    """调用 Suno API 生成背景音乐"""

    def __init__(self):
        self.api_key = settings.SUNO_API_KEY
        if not self.api_key:
            logger.warning("[BGM] SUNO_API_KEY 未配置，BGM 生成功能不可用")

    def generate_bgm(self, description: str) -> str | None:
        """
        根据文本描述生成背景音乐（纯音乐，无人声）。

        :param description: BGM 风格描述，如 "轻快电子乐"、"温馨钢琴"
        :returns: 本地音频文件路径，失败返回 None
        """
        if not self.api_key:
            logger.warning("[BGM] SUNO_API_KEY 未配置，跳过生成")
            return None
        if not description or not description.strip():
            logger.info("[BGM] BGM 描述为空，跳过生成")
            return None

        try:
            # 1. 提交生成任务
            task_id = self._submit_task(description.strip())
            if not task_id:
                return None

            # 2. 轮询等待结果
            audio_url = self._poll_task(task_id)
            if not audio_url:
                return None

            # 3. 下载音频到本地
            local_path = self._download_audio(audio_url)
            logger.info(f"[BGM] 生成完成: {local_path}")
            return local_path

        except Exception as e:
            logger.error(f"[BGM] 生成失败: {e}")
            return None

    def _submit_task(self, description: str) -> str | None:
        """提交 Suno 音乐生成任务，返回 task_id"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "prompt": description,
            "customMode": False,
            "instrumental": True,
            "model": "V4_5ALL",
            "callBackUrl": "http://localhost/callback",
        }

        try:
            resp = requests.post(
                f"{SUNO_BASE_URL}/generate",
                json=payload,
                headers=headers,
                timeout=30,
            )
            result = resp.json()
            if result.get("code") == 200:
                task_id = result["data"]["taskId"]
                logger.info(f"[BGM] 任务已提交: {task_id}")
                return task_id
            else:
                logger.error(f"[BGM] 提交失败: {result.get('msg')}")
                return None
        except Exception as e:
            logger.error(f"[BGM] 请求异常: {e}")
            return None

    def _poll_task(self, task_id: str) -> str | None:
        """轮询任务状态，返回第一个音频的 URL"""
        headers = {"Authorization": f"Bearer {self.api_key}"}
        start_time = time.time()

        while time.time() - start_time < MAX_WAIT_TIME:
            try:
                resp = requests.get(
                    f"{SUNO_BASE_URL}/generate/record-info",
                    params={"taskId": task_id},
                    headers=headers,
                    timeout=15,
                )
                result = resp.json()
                data = result.get("data", {})
                status = data.get("status", "")

                if status == "SUCCESS":
                    audio_list = data.get("response", {}).get("sunoData", [])
                    if audio_list:
                        audio_url = audio_list[0].get("audioUrl") or audio_list[0].get("audio_url")
                        if audio_url:
                            return audio_url
                    logger.warning("[BGM] 任务完成但无音频数据")
                    return None
                elif status == "FAILED":
                    logger.error(f"[BGM] 生成失败: {data.get('errorMessage')}")
                    return None
                else:
                    logger.info(f"[BGM] 状态: {status}，等待中...")

            except Exception as e:
                logger.warning(f"[BGM] 轮询异常: {e}")

            time.sleep(POLL_INTERVAL)

        logger.warning(f"[BGM] 超时（{MAX_WAIT_TIME}秒），放弃等待")
        return None

    def _download_audio(self, audio_url: str) -> str | None:
        """下载音频文件到本地临时目录"""
        try:
            resp = requests.get(audio_url, timeout=60)
            resp.raise_for_status()

            fd, path = tempfile.mkstemp(suffix=".mp3")
            with os.fdopen(fd, "wb") as f:
                f.write(resp.content)
            return path
        except Exception as e:
            logger.error(f"[BGM] 下载失败: {e}")
            return None


# 单例
music_generation_service = MusicGenerationService()
