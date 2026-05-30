"""Image generation service for Ark image APIs."""
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
from backend.v1.app.generate.service.reference_image_utils import (
    MAX_REFERENCE_IMAGES,
    select_reference_images,
)
from backend.store.obj.factory import get_storage_client

logger = logging.getLogger(__name__)

# 鐏北寮曟搸 Ark 骞冲彴鍥剧墖鐢熸垚 API 閰嶇疆
IMAGE_API_URL = "https://ark.cn-beijing.volces.com/api/v3/images/generations"
IMAGE_MODEL = "doubao-seedream-4-5-251128"
IMAGE_SIZE = "1600x2848"


class ImageGenerationService:
    """Generate frame images through Ark image APIs."""

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
        涓烘瘡涓満鏅敓鎴愬浘鐗囥€?

                               渚嬪锛歿"鍟嗗搧涓诲浘": "https://...", "鍟嗗搧缁嗚妭鍥?: ["https://...", "https://..."]}
        """
        # 鎻愬彇绗竴寮犲晢鍝佷富鍥句綔涓哄弬鑰冨浘
        reference_image = None
        if product_images:
            main_imgs = product_images.get("鍟嗗搧涓诲浘", [])
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

                # 浼樺厛浣跨敤 LLM 鐢熸垚鐨?image_prompt锛宖allback 鍒版棫鏍煎紡
                prompt = visual.get("image_prompt") or self._build_image_prompt(source, variables)

                # 璋冪敤鍥剧墖鐢熸垚 API
                if reference_image:
                    # 鏈夊弬鑰冨浘鐗?鈫?鍥剧敓鍥?
                    image_path = self._call_image_to_image(prompt, reference_image)
                else:
                    # 鏃犲弬鑰冨浘鐗?鈫?鏂囩敓鍥?
                    image_path = self._call_text_to_image(prompt)

                # 涓婁紶鍒?TOS 鑾峰彇 HTTP URL
                image_url = self._upload_to_tos(image_path, project_id, i)
                image_urls.append(image_url)

                logger.info(f"[鍥剧墖鐢熸垚] 鍦烘櫙 {i + 1} 鐢熸垚鎴愬姛: {image_url}")
            except Exception as e:
                logger.error(f"[鍥剧墖鐢熸垚] 鍦烘櫙 {i + 1} 鐢熸垚澶辫触: {str(e)}")
                # 浣跨敤鍗犱綅鍥?fallback
                placeholder_path = self._generate_placeholder_image(
                    scene.get("visual", {}).get("variables", {}).get("title", f"鍦烘櫙{i+1}")
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
    ) -> list[Frame]:
        """
        涓烘瘡涓?Frame 骞惰鐢熸垚鍥剧墖锛屽洖濉?image_url 骞舵洿鏂扮姸鎬併€?

        浣跨敤 ThreadPoolExecutor 骞跺彂璋冪敤鍥剧墖 API锛屾瘡甯х嫭绔嬪鐞嗭紝
        鍗曞抚澶辫触涓嶅奖鍝嶅叾浠栧抚銆?

        """
        # 閫夋嫨鍙傝€冨浘锛氫紭鍏堢敤鎴峰弬鑰冨浘锛屽叾娆″晢鍝佷富鍥?
        selected_reference_images = self._select_reference_images(reference_images, product_images)

        # 杩囨护鍑洪渶瑕佺敓鎴愮殑甯э紙璺宠繃宸插畬鎴愮殑锛?
        pending_frames = [f for f in frames if not (f.status == 2 and f.image_url)]
        skipped = len(frames) - len(pending_frames)
        if skipped:
            logger.info(f"[image generation] skipped {skipped} frames with existing images")

        if not pending_frames:
            return frames

        # 鏍囪鎵€鏈夊緟鐢熸垚甯т负"鐢熸垚涓?
        for frame in pending_frames:
            frame.status = 1

        # 骞惰鐢熸垚锛氭瘡甯х嫭绔嬫彁浜ゅ埌绾跨▼姹?
        max_workers = min(4, len(pending_frames))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_frame = {
                executor.submit(self._generate_single_frame, frame, project_id, selected_reference_images): frame
                for frame in pending_frames
            }
            for future in as_completed(future_to_frame):
                frame = future_to_frame[future]
                try:
                    future.result()
                except Exception as e:
                    # _generate_single_frame 宸插鐞?frame 鐘舵€侊紝杩欓噷鍙仛鏃ュ織鍏滃簳
                    logger.error(f"[鍥剧墖鐢熸垚] 甯?{frame.sequence} 绾跨▼寮傚父: {e}")

        return frames

    def _generate_single_frame(
        self,
        frame: Frame,
        project_id: int,
        reference_images: list[str],
    ) -> None:
        """Generate one frame image and update frame status."""
        try:
            prompt = frame.description or ""
            if reference_images:
                prompt = self._build_reference_image_prompt(prompt)
                image_path = self._call_image_to_image(prompt, reference_images)
            else:
                image_path = self._call_text_to_image(prompt)

            image_url = self._upload_to_tos(image_path, project_id, frame.sequence - 1)
            with suppress(OSError):
                os.remove(image_path)
            frame.image_url = image_url
            frame.status = 2  # 宸插畬鎴?
            frame.error_message = None
            logger.info(f"[image generation] frame {frame.sequence} succeeded: {image_url}")
        except Exception as e:
            logger.error(f"[image generation] frame {frame.sequence} failed: {e}")
            # 澶辫触甯т笉鍐欏崰浣?image_url锛岄伩鍏嶄笅娓稿綋浣滅湡瀹為甯ф秷鑰楄棰戦搴?
            frame.image_url = None
            frame.status = 3  # 澶辫触
            frame.error_message = f"image generation failed: {e}"

    def _select_reference_images(
        self,
        reference_images: list[str] | None = None,
        product_images: dict[str, str] | None = None,
    ) -> list[str]:
        """Pick user reference images first, then product images, capped for Ark."""
        # 这里保留一层 service 内部入口，避免旧调用方直接断掉。
        product_refs = product_images.get("閸熷棗鎼ф稉璇叉禈", []) if product_images else None
        return select_reference_images(reference_images, product_refs, limit=MAX_REFERENCE_IMAGES)

    def _select_reference_image(
        self,
        reference_images: list[str] | None = None,
        product_images: dict[str, str] | None = None,
    ) -> str | None:
        """Backward-compatible helper returning the first selected reference."""
        # 历史代码有单图入口，这里继续返回第一张，兼容旧链路。
        images = self._select_reference_images(reference_images, product_images)
        return images[0] if images else None

    def _build_reference_image_prompt(self, prompt: str) -> str:
        return (
            "请参考输入图片中的商品外观、主体形态、颜色和材质，"
            "但按照以下分镜描述重新构图：\n"
            f"{prompt}"
        )


        """Return a product reference image by source key."""





        if not product_images:
            return None

        # 瑙ｆ瀽 source锛屾彁鍙栧浘鐗囩被鍨嬪拰绱㈠紩
        # 渚嬪锛?鍟嗗搧缁嗚妭鍥綶0]" -> type="鍟嗗搧缁嗚妭鍥?, index=0
        if "[" in source and "]" in source:
            parts = source.split("[")
            img_type = parts[0]
            index = int(parts[1].rstrip("]"))
        else:
            img_type = source
            index = 0

        # 浠庡晢鍝佸浘鐗囧簱涓煡鎵?
        if img_type in product_images:
            img_data = product_images[img_type]
            if isinstance(img_data, list):
                return img_data[index] if index < len(img_data) else None
            else:
                return img_data if index == 0 else None

        return None

    def _build_image_prompt(self, source: str, variables: dict) -> str:
        """Build an image prompt from a legacy scene source and variables."""





        title = variables.get("title", "")
        text = variables.get("text", "")

        # 鏋勯€犺缁嗙殑鍥剧墖鎻忚堪
        prompt = f"Ecommerce video image: {source}"
        if title:
            prompt += f", product title: {title}"
        if text:
            prompt += f", scene description: {text}"
        prompt += ". Requirements: high-resolution, professional ecommerce style, suitable for vertical video."

        return prompt

    def _call_text_to_image(self, prompt: str) -> str:
        """Call Ark text-to-image API and return a local image path."""




        # 鏋勯€犺姹傚ご
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        # 鏋勯€犺姹備綋
        payload = {
            "model": IMAGE_MODEL,
            "prompt": prompt,
            "size": IMAGE_SIZE,  # 鏈€灏忓昂瀵歌姹?
            "response_format": "url",
            "sequential_image_generation": "disabled",
            "stream": False,
            "watermark": False,
        }

        # 鍙戦€佽姹?
        response = self._request_with_retry("post", IMAGE_API_URL, json=payload, headers=headers, timeout=60)
        response.raise_for_status()

        # 瑙ｆ瀽鍝嶅簲
        resp_data = response.json()
        if "data" not in resp_data or len(resp_data["data"]) == 0:
            raise Exception("image generation API returned empty data")

        # 鑾峰彇鍥剧墖 URL
        image_url = resp_data["data"][0].get("url")
        if not image_url:
            raise Exception("image generation API did not return an image URL")

        # 涓嬭浇鍥剧墖鍒版湰鍦?
        output_path = os.path.join(self.temp_dir, f"img_{uuid.uuid4().hex}.png")
        self._download_image(image_url, output_path)

        logger.info(f"[text-to-image] API call succeeded: {output_path}")
        return output_path

    def _call_image_to_image(self, prompt: str, reference_image_url: str | list[str]) -> str:
        """Call Ark image-to-image API and return a local image path."""




        # 鏋勯€犺姹傚ご
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        # 鏋勯€犺姹備綋锛堝浘鐢熷浘锛?
        payload = {
            "model": IMAGE_MODEL,
            "prompt": prompt,
            "image": reference_image_url,  # 鍙傝€冨浘鐗?
            "size": IMAGE_SIZE,
            "response_format": "url",
            "sequential_image_generation": "disabled",
            "stream": False,
            "watermark": False,
        }

        # 鍙戦€佽姹?
        response = self._request_with_retry("post", IMAGE_API_URL, json=payload, headers=headers, timeout=60)
        response.raise_for_status()

        # 瑙ｆ瀽鍝嶅簲
        resp_data = response.json()
        if "data" not in resp_data or len(resp_data["data"]) == 0:
            raise Exception("image generation API returned empty data")

        # 鑾峰彇鍥剧墖 URL
        image_url = resp_data["data"][0].get("url")
        if not image_url:
            raise Exception("image generation API did not return an image URL")

        # 涓嬭浇鍥剧墖鍒版湰鍦?
        output_path = os.path.join(self.temp_dir, f"img_{uuid.uuid4().hex}.png")
        self._download_image(image_url, output_path)

        logger.info(f"[image-to-image] API call succeeded: {output_path}")
        return output_path

    def _download_image(self, url: str, local_path: str):
        """Download an image URL to a local path."""




        try:
            response = self._request_with_retry("get", url, stream=True, timeout=30)
            response.raise_for_status()

            with open(local_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
        except Exception as e:
            raise RuntimeError(f"download image failed: {str(e)}")

    def _upload_to_tos(self, local_path: str, project_id: int, scene_index: int) -> str:
        """Upload an image to TOS and return its public URL."""






        object_key = f"projects/{project_id}/scene_{scene_index + 1}.png"
        url = self._upload_with_retry(local_path, object_key)

        # upload_file 宸茶繑鍥炲叕鍏?URL锛岀洿鎺ヤ娇鐢?
        return url

    def _request_with_retry(self, method: str, url: str, **kwargs):
        """Retry external image API/download requests for transient failures."""
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
        """Retry TOS uploads for transient failures."""
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
        """Generate a local placeholder image."""





        output_path = os.path.join(self.temp_dir, f"placeholder_{uuid.uuid4().hex}.png")

        try:
            from PIL import Image, ImageDraw, ImageFont

            # 鍒涘缓 720x1280 鐨勬繁鐏拌壊鑳屾櫙
            img = Image.new("RGB", (720, 1280), (30, 30, 30))
            draw = ImageDraw.Draw(img)

            # 灏濊瘯浣跨敤绯荤粺瀛椾綋
            try:
                font = ImageFont.truetype("arial.ttf", 40)
            except:
                font = ImageFont.load_default()

            # 缁樺埗鍏抽敭璇嶆枃鏈?
            draw.text((360, 640), keyword, fill=(255, 255, 255), font=font, anchor="mm")
            img.save(output_path, "PNG")
        except ImportError:
            # 娌℃湁 PIL 鏃跺垱寤轰竴涓┖鏂囦欢
            with open(output_path, "wb") as f:
                f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        return output_path


image_generation_service = ImageGenerationService()
