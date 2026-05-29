"""图片生成服务（接入火山引擎 Ark 平台）"""
import os
import uuid
import tempfile
import logging

import requests

from backend.v1.app.config.config import settings
from backend.v1.app.models.frame import Frame
from backend.store.obj.factory import get_storage_client

logger = logging.getLogger(__name__)

# 火山引擎 Ark 平台图片生成 API 配置
IMAGE_API_URL = "https://ark.cn-beijing.volces.com/api/v3/images/generations"
IMAGE_MODEL = "doubao-seedream-4-5-251128"


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
    ) -> list[Frame]:
        """
        为每个 Frame 生成图片，回填 image_url 并更新状态。

        :param frames: Frame 对象列表
        :param project_id: 项目 ID
        :param product_images: 商品图片字典（可选），如 {"商品主图": ["url1", "url2"]}
        :returns: 更新后的 Frame 列表
        """
        # 提取第一张商品主图作为参考图
        reference_image = None
        if product_images:
            main_imgs = product_images.get("商品主图", [])
            if isinstance(main_imgs, list) and main_imgs:
                reference_image = main_imgs[0]
            elif isinstance(main_imgs, str) and main_imgs:
                reference_image = main_imgs

        for i, frame in enumerate(frames):
            try:
                if frame.image_url:
                    logger.info(f"[图片生成] 帧 {frame.sequence} 已有图片，跳过重复生成: {frame.image_url}")
                    continue

                frame.status = 1  # 生成中

                # 使用 Frame 的 description 作为图片生成 prompt
                prompt = frame.description or ""

                if reference_image:
                    image_path = self._call_image_to_image(prompt, reference_image)
                else:
                    image_path = self._call_text_to_image(prompt)

                image_url = self._upload_to_tos(image_path, project_id, frame.sequence - 1)
                frame.image_url = image_url
                frame.status = 2  # 已完成
                frame.error_message = None

                logger.info(f"[图片生成] 帧 {frame.sequence} 生成成功: {image_url}")
            except Exception as e:
                logger.error(f"[图片生成] 帧 {frame.sequence} 生成失败: {str(e)}")
                placeholder_path = self._generate_placeholder_image(f"帧{frame.sequence}")
                placeholder_url = self._upload_to_tos(placeholder_path, project_id, frame.sequence - 1)
                frame.image_url = placeholder_url
                frame.status = 3  # 失败
                frame.error_message = f"图片生成失败: {str(e)}"

        return frames

    def _get_reference_image(self, source: str, product_images: dict[str, str] | None) -> str | None:
        """
        从商品图片库中获取参考图片。

        :param source: 图片来源描述（如 "商品主图"、"商品细节图[0]"）
        :param product_images: 商品图片字典
        :returns: 参考图片 URL，未找到返回 None
        """
        if not product_images:
            return None

        # 解析 source，提取图片类型和索引
        # 例如："商品细节图[0]" -> type="商品细节图", index=0
        if "[" in source and "]" in source:
            parts = source.split("[")
            img_type = parts[0]
            index = int(parts[1].rstrip("]"))
        else:
            img_type = source
            index = 0

        # 从商品图片库中查找
        if img_type in product_images:
            img_data = product_images[img_type]
            if isinstance(img_data, list):
                return img_data[index] if index < len(img_data) else None
            else:
                return img_data if index == 0 else None

        return None

    def _build_image_prompt(self, source: str, variables: dict) -> str:
        """
        构造图片生成 prompt。

        :param source: 图片来源描述
        :param variables: 变量（title、text 等）
        :returns: 图片生成 prompt
        """
        title = variables.get("title", "")
        text = variables.get("text", "")

        # 构造详细的图片描述
        prompt = f"电商带货视频配图：{source}"
        if title:
            prompt += f"，商品名称：{title}"
        if text:
            prompt += f"，场景描述：{text}"
        prompt += "。要求：高清、专业电商风格、适合竖屏视频。"

        return prompt

    def _call_text_to_image(self, prompt: str) -> str:
        """
        调用火山引擎 Ark 平台文生图 API。

        :param prompt: 图片描述
        :returns: 生成图片的本地路径
        """
        # 构造请求头
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        # 构造请求体
        payload = {
            "model": IMAGE_MODEL,
            "prompt": prompt,
            "size": "2K",  # 最小尺寸要求
            "response_format": "url",
            "sequential_image_generation": "disabled",
            "stream": False,
            "watermark": False,
        }

        # 发送请求
        response = requests.post(
            IMAGE_API_URL,
            json=payload,
            headers=headers,
            timeout=60,
        )
        response.raise_for_status()

        # 解析响应
        resp_data = response.json()
        if "data" not in resp_data or len(resp_data["data"]) == 0:
            raise Exception("图片生成 API 返回空数据")

        # 获取图片 URL
        image_url = resp_data["data"][0].get("url")
        if not image_url:
            raise Exception("图片生成 API 未返回图片 URL")

        # 下载图片到本地
        output_path = os.path.join(self.temp_dir, f"img_{uuid.uuid4().hex}.png")
        self._download_image(image_url, output_path)

        logger.info(f"[文生图] API 调用成功: {output_path}")
        return output_path

    def _call_image_to_image(self, prompt: str, reference_image_url: str) -> str:
        """
        调用火山引擎 Ark 平台图生图 API。

        :param prompt: 图片描述
        :param reference_image_url: 参考图片 URL
        :returns: 生成图片的本地路径
        """
        # 构造请求头
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        # 构造请求体（图生图）
        payload = {
            "model": IMAGE_MODEL,
            "prompt": prompt,
            "image": reference_image_url,  # 参考图片
            "size": "2K",
            "response_format": "url",
            "sequential_image_generation": "disabled",
            "stream": False,
            "watermark": False,
        }

        # 发送请求
        response = requests.post(
            IMAGE_API_URL,
            json=payload,
            headers=headers,
            timeout=60,
        )
        response.raise_for_status()

        # 解析响应
        resp_data = response.json()
        if "data" not in resp_data or len(resp_data["data"]) == 0:
            raise Exception("图片生成 API 返回空数据")

        # 获取图片 URL
        image_url = resp_data["data"][0].get("url")
        if not image_url:
            raise Exception("图片生成 API 未返回图片 URL")

        # 下载图片到本地
        output_path = os.path.join(self.temp_dir, f"img_{uuid.uuid4().hex}.png")
        self._download_image(image_url, output_path)

        logger.info(f"[图生图] API 调用成功: {output_path}")
        return output_path

    def _download_image(self, url: str, local_path: str):
        """
        下载图片到本地。

        :param url: 图片 URL
        :param local_path: 本地保存路径
        """
        try:
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()

            with open(local_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
        except Exception as e:
            raise RuntimeError(f"下载图片失败: {str(e)}")

    def _upload_to_tos(self, local_path: str, project_id: int, scene_index: int) -> str:
        """
        上传图片到 TOS 获取 HTTP URL。

        :param local_path: 本地图片路径
        :param project_id: 项目 ID
        :param scene_index: 场景索引
        :returns: 图片 HTTP URL
        """
        object_key = f"projects/{project_id}/scene_{scene_index + 1}.png"
        url = get_storage_client().upload_file(local_path, object_key)

        # upload_file 已返回公共 URL，直接使用
        return url

    def _generate_placeholder_image(self, keyword: str) -> str:
        """
        生成占位图片（fallback）。

        :param keyword: 图片关键词
        :returns: 占位图片本地路径
        """
        output_path = os.path.join(self.temp_dir, f"placeholder_{uuid.uuid4().hex}.png")

        try:
            from PIL import Image, ImageDraw, ImageFont

            # 创建 720x1280 的深灰色背景
            img = Image.new("RGB", (720, 1280), (30, 30, 30))
            draw = ImageDraw.Draw(img)

            # 尝试使用系统字体
            try:
                font = ImageFont.truetype("arial.ttf", 40)
            except:
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
