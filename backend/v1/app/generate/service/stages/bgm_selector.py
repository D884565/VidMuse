"""LLM-driven BGM selector service."""
from __future__ import annotations

import json
import logging
import random
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from backend.providers import VolcanoLLM
from backend.providers.dto.schema import ChatMessage, ChatRequest
from backend.v1.app.assets.dao.asset_dao import AssetDAO
from backend.v1.app.models.asset import Asset

logger = logging.getLogger(__name__)

BGM_SELECT_PROMPT = """你是 BGM 选曲助手。根据视频风格信息，从候选列表中选择最匹配的背景音乐。

视频风格信息:
{style_info}

候选 BGM（共 {count} 首）:
{candidates}

只返回一个 JSON，不要其他内容：
{{"bgm_id": <id>, "reason": "选曲理由(10字内)"}}"""

MAX_CANDIDATES = 20
BGM_LIBRARY_SCOPES = ("bgm_library", "library")


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
        """从 BGM 库中选择最匹配的背景音乐。"""
        style_info = self._extract_style_info(script_content)
        if not style_info:
            logger.info("[BGM选曲] 无风格信息，跳过")
            return None

        candidates = self._get_candidates(db, exclude_ids)
        if not candidates:
            logger.info("[BGM选曲] BGM 库为空，跳过")
            return None

        scored = self._score_candidates(style_info, candidates)
        top_candidates = scored[:MAX_CANDIDATES]

        try:
            bgm_id = self._llm_select(style_info, top_candidates)
            if bgm_id:
                logger.info("[BGM选曲] LLM 选择了 bgm_id=%s", bgm_id)
                return bgm_id
        except Exception as exc:
            logger.warning("[BGM选曲] LLM 调用失败，降级到标签匹配: %s", exc)

        if top_candidates:
            top_score = top_candidates[0].get("_score", 0)
            top_tier = [c for c in top_candidates if c.get("_score", 0) == top_score]
            chosen = random.choice(top_tier)
            logger.info(
                "[BGM选曲] 随机选择 bgm_id=%s (top_tier %d 首, score=%d)",
                chosen["id"],
                len(top_tier),
                top_score,
            )
            return chosen["id"]

        return None

    async def select_bgm_async(
        self,
        db: AsyncSession,
        script_content: dict,
        exclude_ids: list[int] | None = None,
    ) -> int | None:
        """AsyncSession 版 BGM 选曲。"""
        style_info = self._extract_style_info(script_content)
        if not style_info:
            logger.info("[BGM选曲] 无风格信息，跳过")
            return None

        candidates = await self._get_candidates_async(db, exclude_ids)
        if not candidates:
            logger.info("[BGM选曲] BGM 库为空，跳过")
            return None

        scored = self._score_candidates(style_info, candidates)
        top_candidates = scored[:MAX_CANDIDATES]

        try:
            bgm_id = self._llm_select(style_info, top_candidates)
            if bgm_id:
                logger.info("[BGM选曲] LLM 选择了 bgm_id=%s", bgm_id)
                return bgm_id
        except Exception as exc:
            logger.warning("[BGM选曲] LLM 调用失败，降级到标签匹配: %s", exc)

        if top_candidates:
            top_score = top_candidates[0].get("_score", 0)
            top_tier = [c for c in top_candidates if c.get("_score", 0) == top_score]
            chosen = random.choice(top_tier)
            logger.info(
                "[BGM选曲] 随机选择 bgm_id=%s (top_tier %d 首, score=%d)",
                chosen["id"],
                len(top_tier),
                top_score,
            )
            return chosen["id"]

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
        assets: list[Asset] = []
        for scope in BGM_LIBRARY_SCOPES:
            _, rows = AssetDAO.list_assets(db, type=3, scope=scope, page_size=200)
            assets = [row[0] for row in rows]
            if assets:
                break
        return self._assets_to_candidates(assets, exclude_ids)

    async def _get_candidates_async(self, db: AsyncSession, exclude_ids: list[int] | None) -> list[dict]:
        """从异步数据库会话获取 BGM 候选列表。"""
        result = await db.execute(
            select(Asset)
            .where(
                Asset.type == 3,
                or_(*[Asset.scope["type"].as_string() == scope for scope in BGM_LIBRARY_SCOPES]),
            )
            .order_by(Asset.created_at.desc())
            .limit(200)
        )
        return self._assets_to_candidates(result.scalars().all(), exclude_ids)

    def _assets_to_candidates(self, assets: list[Asset], exclude_ids: list[int] | None) -> list[dict]:
        candidates = []
        exclude_set = set(exclude_ids or [])
        for asset in assets:
            if asset.id in exclude_set:
                continue
            tags = asset.tags or {}
            candidates.append(
                {
                    "id": asset.id,
                    "title": asset.title or "",
                    "duration": asset.duration,
                    "emotion": tags.get("emotion", []),
                    "scene": tags.get("scene", []),
                    "style": tags.get("style", []),
                    "tempo": tags.get("tempo", ""),
                    "energy": tags.get("energy", ""),
                }
            )
        return candidates

    def _score_candidates(self, style_info: str, candidates: list[dict]) -> list[dict]:
        """按标签重叠度给候选 BGM 评分排序。"""
        style_lower = style_info.lower()

        keywords = set()
        for word in style_info.replace("\n", " ").split():
            word = word.strip(",:;，。：；")
            if len(word) >= 2:
                keywords.add(word)

        scored = []
        for candidate in candidates:
            score = 0
            all_tags = candidate.get("emotion", []) + candidate.get("scene", []) + candidate.get("style", [])
            for tag in all_tags:
                if tag.lower() in style_lower or any(keyword in tag for keyword in keywords):
                    score += 2
            if candidate.get("tempo") and candidate["tempo"] in style_lower:
                score += 1
            if candidate.get("energy") and candidate["energy"] in style_lower:
                score += 1
            candidate["_score"] = score
            scored.append(candidate)

        scored.sort(key=lambda item: item["_score"], reverse=True)
        return scored

    def _llm_select(self, style_info: str, candidates: list[dict]) -> int | None:
        """调用 LLM 从候选中选择最佳 BGM。"""
        candidate_lines = []
        for candidate in candidates:
            tags_str = []
            if candidate["emotion"]:
                tags_str.append(f"情绪:{','.join(candidate['emotion'])}")
            if candidate["scene"]:
                tags_str.append(f"场景:{','.join(candidate['scene'])}")
            if candidate["style"]:
                tags_str.append(f"风格:{','.join(candidate['style'])}")
            tag_line = " | ".join(tags_str) if tags_str else "无标签"
            duration = f"{candidate['duration']}s" if candidate.get("duration") else ""
            candidate_lines.append(f"  [id={candidate['id']}] {candidate['title']} {duration} | {tag_line}")

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

        result: dict[str, Any] = json.loads(content)
        bgm_id = result.get("bgm_id")

        valid_ids = {candidate["id"] for candidate in candidates}
        if bgm_id and bgm_id in valid_ids:
            return bgm_id

        return None


bgm_selector_service = BGMSelectorService()
