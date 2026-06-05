"""LLM 驱动的 BGM 选曲服务：根据剧本风格从 BGM 库中选择最匹配的背景音乐。"""
from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from backend.providers import VolcanoLLM
from backend.providers.dto.schema import ChatRequest, ChatMessage
from backend.v1.app.assets.dao.asset_dao import AssetDAO

logger = logging.getLogger(__name__)

BGM_SELECT_PROMPT = """你是 BGM 选曲助手。根据视频风格信息，从候选列表中选择最匹配的背景音乐。

视频风格信息:
{style_info}

候选 BGM（共 {count} 首）:
{candidates}

只返回一个 JSON，不要其他内容:
{{"bgm_id": <id>, "reason": "选曲理由(10字内)"}}"""

MAX_CANDIDATES = 20


class BGMSelectorService:
    """根据剧本风格从 BGM 库中选择背景音乐。"""

    def __init__(self):
        self._llm = None

    @property
    def llm(self):
        if self._llm is None:
            if VolcanoLLM is None:
                raise RuntimeError("VolcanoLLM 不可用")
            self._llm = VolcanoLLM(key=None, model_name=None)
        return self._llm

    def select_bgm(
        self,
        db: Session,
        script_content: dict,
        exclude_ids: list[int] | None = None,
    ) -> int | None:
        """从 BGM 库中选择最匹配的背景音乐。

        Args:
            db: 同步数据库会话
            script_content: 剧本内容 dict，包含 video_meta, scenes, audio 等
            exclude_ids: 排除的 BGM ID（用于"换一首"场景）

        Returns:
            选中的 BGM Asset ID，或 None（无合适 BGM 时）
        """
        # 1. 提取风格信号
        style_info = self._extract_style_info(script_content)
        if not style_info:
            logger.info("[BGM选曲] 无风格信息，跳过")
            return None

        # 2. 获取 BGM 候选
        candidates = self._get_candidates(db, exclude_ids)
        if not candidates:
            logger.info("[BGM选曲] BGM 库为空，跳过")
            return None

        # 3. 预筛选（按标签重叠度评分，取 top N）
        scored = self._score_candidates(style_info, candidates)
        top_candidates = scored[:MAX_CANDIDATES]

        # 4. LLM 选曲
        try:
            bgm_id = self._llm_select(style_info, top_candidates)
            if bgm_id:
                logger.info("[BGM选曲] LLM 选择了 bgm_id=%s", bgm_id)
                return bgm_id
        except Exception as exc:
            logger.warning("[BGM选曲] LLM 调用失败，降级到标签匹配: %s", exc)

        # 5. 降级：取评分最高的候选
        if top_candidates:
            fallback_id = top_candidates[0]["id"]
            logger.info("[BGM选曲] 降级选择评分最高的 bgm_id=%s", fallback_id)
            return fallback_id

        return None

    def _extract_style_info(self, script_content: dict) -> str:
        """从剧本内容中提取风格描述文本。"""
        parts = []

        video_meta = script_content.get("video_meta", {})
        if video_meta.get("style"):
            parts.append(f"视频风格: {video_meta['style']}")
        if video_meta.get("hook_line"):
            parts.append(f"开场文案: {video_meta['hook_line']}")

        audio = script_content.get("audio", {})
        if audio.get("bgm"):
            parts.append(f"BGM需求: {audio['bgm']}")

        scenes = script_content.get("scenes", [])
        moods = set()
        voice_styles = set()
        for scene in scenes:
            visual = scene.get("visual", {})
            if visual.get("mood"):
                moods.add(visual["mood"])
            if scene.get("voice_style"):
                voice_styles.add(scene["voice_style"])
        if moods:
            parts.append(f"画面氛围: {', '.join(moods)}")
        if voice_styles:
            parts.append(f"配音风格: {', '.join(voice_styles)}")

        return "\n".join(parts)

    def _get_candidates(self, db: Session, exclude_ids: list[int] | None) -> list[dict]:
        """从数据库获取 BGM 候选列表。"""
        _, assets = AssetDAO.list_assets(
            db, type=3, scope="bgm_library", page_size=200
        )
        candidates = []
        exclude_set = set(exclude_ids or [])
        for asset in assets:
            if asset.id in exclude_set:
                continue
            tags = asset.tags or {}
            candidates.append({
                "id": asset.id,
                "title": asset.title or "",
                "duration": asset.duration,
                "emotion": tags.get("emotion", []),
                "scene": tags.get("scene", []),
                "style": tags.get("style", []),
                "tempo": tags.get("tempo", ""),
                "energy": tags.get("energy", ""),
            })
        return candidates

    def _score_candidates(self, style_info: str, candidates: list[dict]) -> list[dict]:
        """按标签重叠度给候选 BGM 评分排序。"""
        style_lower = style_info.lower()

        # 从风格信息中提取关键词
        keywords = set()
        for word in style_info.replace("\n", " ").split():
            word = word.strip(",:;，。：；")
            if len(word) >= 2:
                keywords.add(word)

        scored = []
        for c in candidates:
            score = 0
            all_tags = (
                c.get("emotion", [])
                + c.get("scene", [])
                + c.get("style", [])
            )
            for tag in all_tags:
                if tag.lower() in style_lower or any(kw in tag for kw in keywords):
                    score += 2
            if c.get("tempo") and c["tempo"] in style_lower:
                score += 1
            if c.get("energy") and c["energy"] in style_lower:
                score += 1
            c["_score"] = score
            scored.append(c)

        scored.sort(key=lambda x: x["_score"], reverse=True)
        return scored

    def _llm_select(self, style_info: str, candidates: list[dict]) -> int | None:
        """调用 LLM 从候选中选择最佳 BGM。"""
        candidate_lines = []
        for c in candidates:
            tags_str = []
            if c["emotion"]:
                tags_str.append(f"情绪:{','.join(c['emotion'])}")
            if c["scene"]:
                tags_str.append(f"场景:{','.join(c['scene'])}")
            if c["style"]:
                tags_str.append(f"风格:{','.join(c['style'])}")
            tag_line = " | ".join(tags_str) if tags_str else "无标签"
            dur = f"{c['duration']}s" if c.get("duration") else ""
            candidate_lines.append(f"  [id={c['id']}] {c['title']} {dur} | {tag_line}")

        prompt = BGM_SELECT_PROMPT.format(
            style_info=style_info,
            count=len(candidates),
            candidates="\n".join(candidate_lines),
        )

        request = ChatRequest(
            messages=[ChatMessage(role="system", content=prompt)],
            temperature=0.3,
            max_tokens=100,
        )
        response = self.llm._chat(request)
        content = response.content.strip()

        # 解析 JSON（处理 markdown 代码块）
        if content.startswith("```"):
            lines = content.split("\n")
            json_lines = []
            in_block = False
            for line in lines:
                if line.strip().startswith("```"):
                    in_block = not in_block
                    continue
                if in_block:
                    json_lines.append(line)
            content = "\n".join(json_lines).strip()

        result = json.loads(content)
        bgm_id = result.get("bgm_id")

        # 验证 ID 在候选列表中
        valid_ids = {c["id"] for c in candidates}
        if bgm_id and bgm_id in valid_ids:
            return bgm_id

        return None


bgm_selector_service = BGMSelectorService()
