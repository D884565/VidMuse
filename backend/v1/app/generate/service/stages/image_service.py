"""图片生成服务（接入火山引擎 Ark 平台）"""
import os
import uuid
import tempfile
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import suppress

import requests

from backend.v1.app.config.config import settings
from backend.v1.app.models.frame import Frame
from backend.v1.app.generate.service.generateUtils.reference_image_utils import (
    MAX_REFERENCE_IMAGES,
    select_reference_images,
)
from backend.v1.app.generate.service.workflow.media_resolvers import resolve_image_generation_prompt
from backend.store.obj.factory import get_storage_client

logger = logging.getLogger(__name__)

# 火山引擎 Ark 平台图片生成 API 配置
IMAGE_API_URL = "https://ark.cn-beijing.volces.com/api/v3/images/generations"
IMAGE_MODEL = "doubao-seedream-4-5-251128"
IMAGE_SIZE = "1600x2848"


class ImageGenerationService:
    """图片生成服务（火山引擎 Ark 平台）"""

    def __init__(self):
        self.temp_dir = tempfile.gettempdir()
        self.api_key = settings.IMAGE_API_KEY

    def generate_scene_images(
        self,
        scenes: list[dict],
        project_id: int,
        product_images: dict[str, str] | None = None,
    ) -> list[str]:
        """
        为每个场景生成图片。

        :param scenes: 场景列表（包含 visual 字段）
        :param project_id: 项目 ID
        :param product_images: 商品图片字典（可选），key 为图片类型，value 为图片 URL
                               例如：{"商品主图": "https://...", "商品细节图": ["https://...", "https://..."]}
        :returns: 图片 HTTP URL 列表
        """
        # 提取第一张商品主图作为参考图
        reference_image = None
        if product_images:
            main_imgs = product_images.get("商品主图", [])
            if isinstance(main_imgs, list) and main_imgs:
                reference_image = main_imgs[0]
            elif isinstance(main_imgs, str) and main_imgs:
                reference_image = main_imgs

        image_urls = []
        for i, scene in enumerate(scenes):
            try:
                visual = scene.get("visual", {})
                variables = visual.get("variables", {})
                source = visual.get("source", "")

                # 优先使用 LLM 生成的 image_prompt，fallback 到旧格式
                prompt = visual.get("image_prompt") or self._build_image_prompt(source, variables)

                # 调用图片生成 API
                if reference_image:
                    # 有参考图片 → 图生图
                    image_path = self._call_image_to_image(prompt, reference_image)
                else:
                    # 无参考图片 → 文生图
                    image_path = self._call_text_to_image(prompt)

                # 上传到 TOS 获取 HTTP URL
                image_url = self._upload_to_tos(image_path, project_id, i)
                image_urls.append(image_url)

                logger.info(f"[图片生成] 场景 {i + 1} 生成成功: {image_url}")
            except Exception as e:
                logger.error(f"[图片生成] 场景 {i + 1} 生成失败: {str(e)}")
                # 使用占位图 fallback
                placeholder_path = self._generate_placeholder_image(
                    scene.get("visual", {}).get("variables", {}).get("title", f"场景{i+1}")
                )
                placeholder_url = self._upload_to_tos(placeholder_path, project_id, i)
                image_urls.append(placeholder_url)

        return image_urls

    def generate_frame_images(
        self,
        frames: list[Frame],
        project_id: int,
        product_images: dict[str, str] | None = None,
        reference_images: list[str] | None = None,
        style: str | None = None,
    ) -> list[Frame]:
        """
        为每个 Frame 并行生成图片，回填 image_url 并更新状态。

        使用 ThreadPoolExecutor 并发调用图片 API，每帧独立处理，
        单帧失败不影响其他帧。

        :param frames: Frame 对象列表
        :param project_id: 项目 ID
        :param product_images: 商品图片字典（可选），如 {"商品主图": ["url1", "url2"]}
        :param reference_images: 用户上传的参考图片 URL 列表（可选）
        :returns: 更新后的 Frame 列表
        """
        # 选择参考图：优先用户参考图，其次商品主图
        selected_reference_images = self._select_reference_images(reference_images, product_images)

        # 过滤出需要生成的帧（跳过已完成的）
        pending_frames = [f for f in frames if not (f.status == 2 and f.image_url and not getattr(f, "dirty", 0))]
        skipped = len(frames) - len(pending_frames)
        if skipped:
            logger.info(f"[image generation] skipped {skipped} frames with existing images")

        if not pending_frames:
            return frames

        # 标记所有待生成帧为"生成中"
        for frame in pending_frames:
            frame.status = 1

        # 并行生成：每帧独立提交到线程池
        max_workers = min(5, len(pending_frames))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_frame = {
                executor.submit(self._generate_single_frame, frame, project_id, selected_reference_images, style): frame
                for frame in pending_frames
            }
            for future in as_completed(future_to_frame):
                frame = future_to_frame[future]
                try:
                    future.result()
                except Exception as e:
                    # _generate_single_frame 已处理 frame 状态，这里只做日志兜底
                    logger.error(f"[图片生成] 帧 {frame.sequence} 线程异常: {e}")

        return frames

    def _generate_single_frame(
        self,
        frame: Frame,
        project_id: int,
        reference_images: list[str],
        style: str | None = None,
    ) -> None:
        """生成单帧图片并回填状态。成功写入 frame.status=2，失败写入 frame.status=3。"""
        try:
            prompt = resolve_image_generation_prompt(frame, style=style)
            if reference_images:
                prompt = self._build_reference_image_prompt(prompt)
                image_path = self._call_image_to_image(prompt, reference_images)
            else:
                image_path = self._call_text_to_image(prompt)

            image_url = self._upload_to_tos(image_path, project_id, frame.sequence - 1)
            with suppress(OSError):
                os.remove(image_path)
            frame.image_url = image_url
            frame.status = 2  # 已完成
            frame.error_message = None
            logger.info(f"[image generation] frame {frame.sequence} succeeded: {image_url}")
        except Exception as e:
            logger.error(f"[image generation] frame {frame.sequence} failed: {e}")
            # 失败帧不写占位 image_url，避免下游当作真实首帧消耗视频额度
            frame.image_url = None
            frame.status = 3  # 失败
            frame.error_message = f"image generation failed: {e}"

    def _select_reference_images(
        self,
        reference_images: list[str] | None = None,
        product_images: dict[str, str] | None = None,
    ) -> list[str]:
        """优先选择用户参考图，再选商品图片，数量受 Ark 限制。"""
        product_refs = product_images.get("商品主图", []) if product_images else None
        return select_reference_images(reference_images, product_refs, limit=MAX_REFERENCE_IMAGES)

    def _select_reference_image(
        self,
        reference_images: list[str] | None = None,
        product_images: dict[str, str] | None = None,
    ) -> str | None:
        """向后兼容的辅助方法，返回第一个选中的参考图。"""
        images = self._select_reference_images(reference_images, product_images)
        return images[0] if images else None

    def _build_reference_image_prompt(self, prompt: str) -> str:
        """构建图生图的提示词，要求参考商品外观但按分镜描述重新构图。"""
        return (
            "请参考输入图片中的商品外观、主体形态、颜色和材质，"
            "但按照以下分镜描述重新构图：\n"
            f"{prompt}"
        )

    def _build_image_prompt(self, source: str, variables: dict) -> str:
        """从旧格式场景数据构造图片生成 prompt。"""
        title = variables.get("title", "")
        text = variables.get("text", "")

        prompt = f"电商带货视频配图：{source}"
        if title:
            prompt += f"，商品名称：{title}"
        if text:
            prompt += f"，场景描述：{text}"
        prompt += "。要求：高清、专业电商风格、适合竖屏视频。"

        return prompt

    def _call_text_to_image(self, prompt: str) -> str:
        """调用火山引擎 Ark 平台文生图 API，返回本地图片路径。"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        payload = {
            "model": IMAGE_MODEL,
            "prompt": prompt,
            "size": IMAGE_SIZE,
            "response_format": "url",
            "sequential_image_generation": "disabled",
            "stream": False,
            "watermark": False,
        }

        response = self._request_with_retry("post", IMAGE_API_URL, json=payload, headers=headers, timeout=60)
        response.raise_for_status()

        resp_data = response.json()
        if "data" not in resp_data or len(resp_data["data"]) == 0:
            raise Exception("图片生成 API 返回空数据")

        image_url = resp_data["data"][0].get("url")
        if not image_url:
            raise Exception("图片生成 API 未返回图片 URL")

        output_path = os.path.join(self.temp_dir, f"img_{uuid.uuid4().hex}.png")
        self._download_image(image_url, output_path)

        logger.info(f"[文生图] API 调用成功: {output_path}")
        return output_path

    def _call_image_to_image(self, prompt: str, reference_image_url: str | list[str]) -> str:
        """调用火山引擎 Ark 平台图生图 API，返回本地图片路径。"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        payload = {
            "model": IMAGE_MODEL,
            "prompt": prompt,
            "image": reference_image_url,  # 参考图片
            "size": IMAGE_SIZE,
            "response_format": "url",
            "sequential_image_generation": "disabled",
            "stream": False,
            "watermark": False,
        }

        response = self._request_with_retry("post", IMAGE_API_URL, json=payload, headers=headers, timeout=60)
        response.raise_for_status()

        resp_data = response.json()
        if "data" not in resp_data or len(resp_data["data"]) == 0:
            raise Exception("图片生成 API 返回空数据")

        image_url = resp_data["data"][0].get("url")
        if not image_url:
            raise Exception("图片生成 API 未返回图片 URL")

        output_path = os.path.join(self.temp_dir, f"img_{uuid.uuid4().hex}.png")
        self._download_image(image_url, output_path)

        logger.info(f"[图生图] API 调用成功: {output_path}")
        return output_path

    def _download_image(self, url: str, local_path: str):
        """下载图片到本地。"""
        try:
            response = self._request_with_retry("get", url, stream=True, timeout=30)
            response.raise_for_status()

            with open(local_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
        except Exception as e:
            raise RuntimeError(f"下载图片失败: {str(e)}")

    def _upload_to_tos(self, local_path: str, project_id: int, scene_index: int) -> str:
        """上传图片到 TOS 并返回公共 URL。"""
        object_key = f"projects/{project_id}/scene_{scene_index + 1}.png"
        url = self._upload_with_retry(local_path, object_key)
        return url

    def _request_with_retry(self, method: str, url: str, **kwargs):
        """对外部图片 API/下载增加短重试，减少瞬时 429/5xx 对整批任务的影响。"""
        last_exc = None
        for attempt in range(3):
            try:
                response = requests.request(method, url, **kwargs)
                response.raise_for_status()
                return response
            except Exception as exc:
                last_exc = exc
                if attempt == 2:
                    break
                time.sleep(0.5 * (2 ** attempt))
        raise last_exc

    def _upload_with_retry(self, local_path: str, object_key: str) -> str:
        """TOS 上传可能受网络抖动影响，短重试后仍失败再交给上层标记帧失败。"""
        last_exc = None
        for attempt in range(3):
            try:
                return get_storage_client().upload_file(local_path, object_key)
            except Exception as exc:
                last_exc = exc
                if attempt == 2:
                    break
                time.sleep(0.5 * (2 ** attempt))
        raise last_exc

    def _generate_placeholder_image(self, keyword: str) -> str:
        """生成本地占位图片（fallback）。"""
        output_path = os.path.join(self.temp_dir, f"placeholder_{uuid.uuid4().hex}.png")

        try:
            from PIL import Image, ImageDraw, ImageFont

            # 创建 720x1280 的深灰色背景
            img = Image.new("RGB", (720, 1280), (30, 30, 30))
            draw = ImageDraw.Draw(img)

            # 尝试使用系统字体
            try:
                font = ImageFont.truetype("arial.ttf", 40)
            except Exception:
                font = ImageFont.load_default()

            # 绘制关键词文本
            draw.text((360, 640), keyword, fill=(255, 255, 255), font=font, anchor="mm")
            img.save(output_path, "PNG")
        except ImportError:
            # 没有 PIL 时创建一个空文件
            with open(output_path, "wb") as f:
                f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        return output_path


image_generation_service = ImageGenerationService()
