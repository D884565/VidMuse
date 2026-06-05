"""为新创建的项目构建初始对话消息。"""
from __future__ import annotations

from typing import Any


class ProjectInitialMessageBuilder:
    """将项目创建时的字段转换为用户视角的对话消息。

    生成的消息包含文字内容（摘要所有创建参数）和结构化 blocks（商品卡片、素材网格）。
    """

    def build(
        self,
        *,
        title: str,
        user_prompt: str | None,
        style: str | None,
        target_audience: str | None,
        key_points: list[str] | None,
        avoid: list[str] | None,
        target_duration: int | None,
        voice_type: str | None,
        product_url: str | None,
        reference_images: list[str] | None,
        product_info: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """构建初始消息，返回包含 role/content/blocks/metadata 的字典。"""
        content = self._build_content(
            title=title,
            user_prompt=user_prompt,
            style=style,
            target_audience=target_audience,
            key_points=key_points or [],
            avoid=avoid or [],
            target_duration=target_duration,
            voice_type=voice_type,
            product_url=product_url,
            product_info=product_info,
        )
        blocks = self._build_blocks(
            product_url=product_url,
            reference_images=reference_images or [],
            product_info=product_info,
        )
        return {
            "role": "user",
            "content": content,
            "message_type": "asset",
            "stage": "project_start",
            "blocks": blocks,
            "metadata": {
                "source": "project_create",
                "has_assets": any(block.get("type") == "asset_grid" for block in blocks),
            },
        }

    def _build_content(
        self,
        *,
        title: str,
        user_prompt: str | None,
        style: str | None,
        target_audience: str | None,
        key_points: list[str],
        avoid: list[str],
        target_duration: int | None,
        voice_type: str | None,
        product_url: str | None,
        product_info: dict[str, Any] | None,
    ) -> str:
        """拼接文字摘要：将所有创建参数汇总为一条可读的用户消息。"""
        parts: list[str] = []
        prompt = (user_prompt or "").strip()
        parts.append(prompt or f"创建视频项目：{title}")

        product_title = (product_info or {}).get("title")
        if product_title:
            parts.append(f"商品：{product_title}")
        elif product_url:
            parts.append(f"商品链接：{product_url}")

        if style:
            parts.append(f"风格：{style}")
        if target_audience:
            parts.append(f"目标受众：{target_audience}")
        if key_points:
            parts.append(f"重点卖点：{'、'.join(item for item in key_points if item)}")
        if avoid:
            parts.append(f"避免内容：{'、'.join(item for item in avoid if item)}")
        if target_duration:
            parts.append(f"时长：约 {target_duration} 秒")
        if voice_type:
            parts.append(f"音色：{voice_type}")

        return "；".join(part for part in parts if part)

    def _build_blocks(
        self,
        *,
        product_url: str | None,
        reference_images: list[str],
        product_info: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        """构建结构化 blocks：商品卡片 + 素材网格（参考图和商品图）。"""
        blocks: list[dict[str, Any]] = []
        # 商品卡片
        if product_info or product_url:
            blocks.append({
                "type": "product_card",
                "title": (product_info or {}).get("title") or "商品链接",
                "description": (product_info or {}).get("description"),
                "url": product_url,
            })

        # 素材网格：参考图 + 商品图
        asset_items: list[dict[str, Any]] = []
        for index, url in enumerate(reference_images, 1):
            if url:
                asset_items.append({
                    "type": "image",
                    "source": "reference_image",
                    "title": f"参考图 {index}",
                    "url": url,
                    "thumbnail_url": url,
                })

        for index, url in enumerate(self._product_images(product_info), 1):
            asset_items.append({
                "type": "image",
                "source": "product_image",
                "title": f"商品图 {index}",
                "url": url,
                "thumbnail_url": url,
            })

        if asset_items:
            blocks.append({
                "type": "asset_grid",
                "items": asset_items,
            })

        return blocks

    def _product_images(self, product_info: dict[str, Any] | None) -> list[str]:
        """从商品信息中提取所有图片 URL（主图、详情图、通用图片字段）。"""
        if not product_info:
            return []
        images: list[str] = []
        for key in ("main_images", "detail_images", "images"):
            value = product_info.get(key)
            if isinstance(value, list):
                images.extend(str(item) for item in value if item)
            elif isinstance(value, str) and value:
                images.append(value)
        return images

    def build_system_intro(self) -> dict[str, Any]:
        """构建系统介绍消息，在项目创建时作为第一条助手消息存储。"""
        return {
            "role": "assistant",
            "content": "欢迎使用带货视频生成系统！我将帮助您一步步创建带货短视频：\n\n"
                       "1. 剧本创作 - 根据您的产品和需求生成分镜脚本\n"
                       "2. 分镜配图 - 为每个分镜生成精美的画面\n"
                       "3. 视频成片 - 将所有分镜合成为最终视频\n\n"
                       "请描述您想要推广的产品，我会为您开始创作。",
            "message_type": "system_intro",
            "stage": "project_start",
            "blocks": [],
            "metadata": {
                "source": "system",
                "is_intro": True,
            },
        }


project_initial_message_builder = ProjectInitialMessageBuilder()
