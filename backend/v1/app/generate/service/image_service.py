"""图片处理服务"""
import os
import uuid
import tempfile


class ImageService:
    """场景配图处理服务（当前返回 Mock 图片）"""

    def __init__(self):
        self.temp_dir = tempfile.gettempdir()

    def prepare_scene_images(self, script_content: dict) -> list[str]:
        """
        为剧本每个场景准备配图。

        :param script_content: 剧本 JSON
        :returns: 各场景图片的本地路径列表（后续上传 MinIO）
        """
        images = []
        for scene in script_content.get("body", []):
            image_path = self._create_placeholder_image(scene.get("image_keyword", "default"))
            images.append(image_path)
        return images

    def _create_placeholder_image(self, keyword: str) -> str:
        """创建占位图片（后续替换为真实图片搜索/生成）"""
        output_path = os.path.join(self.temp_dir, f"img_{uuid.uuid4().hex}.png")
        self._generate_placeholder_png(output_path, keyword)
        return output_path

    def _generate_placeholder_png(self, path: str, keyword: str):
        """生成一个简单的占位 PNG（后续替换为真实图片）"""
        try:
            from PIL import Image, ImageDraw
            img = Image.new("RGB", (1280, 720), (30, 30, 30))
            draw = ImageDraw.Draw(img)
            draw.text((640, 360), keyword, fill=(255, 255, 255))
            img.save(path, "PNG")
        except ImportError:
            # 没有 PIL 时创建一个空文件
            with open(path, "wb") as f:
                f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)


image_service = ImageService()
