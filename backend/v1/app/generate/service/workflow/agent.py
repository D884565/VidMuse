"""规则优先的工作流 Agent：将用户自然语言映射为可执行的项目动作。"""
from __future__ import annotations

import re


class WorkflowAgentService:
    """将用户自然语言映射为可执行的工作流动作。

    第一版按规则优先：确认、生成、重生成这类高频意图不需要 LLM。
    只有规则无法判断时才返回澄清动作，避免误触发昂贵的视频生成。
    """

    def plan(self, project, frames: list, content: str, frame_id: int | None = None) -> dict:
        """根据用户输入和项目当前阶段，返回一个动作计划。"""
        text = (content or "").strip()
        stage = getattr(project, "workflow_stage", None) or "created"
        selected_frame_ids = self._resolve_frame_ids(frames, text, frame_id)
        project_regeneration_action = None
        if stage in {"image", "video", "completed"}:
            project_regeneration_action = self._project_regeneration_action(text)
        if project_regeneration_action:
            stage_map = {
                "REGENERATE_PROJECT_ALL": "script",
                "REGENERATE_IMAGES_AND_VIDEO": "image",
                "REGENERATE_VIDEO_ONLY": "video",
            }
            reply_map = {
                "REGENERATE_PROJECT_ALL": "我理解你想把这个项目从剧本开始全部重跑。这个操作会重新生成剧本、图片和视频，可以继续吗？",
                "REGENERATE_IMAGES_AND_VIDEO": "我理解你想保留剧本，只重新生成图片和视频。这个操作会替换现有首帧图和成片，可以继续吗？",
                "REGENERATE_VIDEO_ONLY": "我理解你想保留剧本和图片，只重新生成视频成片。这个操作会重跑视频片段和最终合成，可以继续吗？",
            }
            return self._plan(
                project_regeneration_action,
                affected_stage=stage_map[project_regeneration_action],
                next_stage=stage_map[project_regeneration_action],
                requires_confirmation=True,
                assistant_content=reply_map[project_regeneration_action],
            )

        # 优先判断：用户想重生成某张图片
        if self._wants_image_regeneration(text, selected_frame_ids):
            return self._plan(
                "REGENERATE_FRAME_IMAGE",
                affected_stage="image",
                affected_frame_ids=selected_frame_ids,
                next_stage="image",
                assistant_content="我会按你的要求重生成对应分镜图片，视频阶段会先标记为失效。",
            )

        # 判断换 BGM 意图
        if self._wants_change_bgm(text):
            return self._plan(
                "CHANGE_BGM",
                affected_stage=stage,
                assistant_content="好的，我来为你重新选择背景音乐。",
            )

        if self._wants_tts_regeneration(text):
            return self._plan(
                "REGENERATE_TTS",
                affected_stage="video",
                next_stage="video",
                assistant_content="好的，我会按你的要求重新生成配音。",
            )

        # 判断确认意图：根据当前阶段分发到不同的确认动作
        if self._has_confirm_intent(text):
            if stage == "script" and self._mentions_image_or_next(text):
                return self._plan(
                    "CONFIRM_SCRIPT_AND_GENERATE_IMAGES",
                    affected_stage="script",
                    next_stage="image",
                    assistant_content="剧本已确认，我会开始生成分镜图片。",
                )
            if stage == "image" and self._mentions_video_or_next(text):
                return self._plan(
                    "CONFIRM_IMAGES_AND_GENERATE_VIDEO",
                    affected_stage="image",
                    next_stage="video",
                    assistant_content="图片已确认，我会开始生成最终视频。",
                )
            if stage == "video":
                return self._plan(
                    "CONFIRM_VIDEO",
                    affected_stage="video",
                    next_stage="completed",
                    assistant_content="视频已确认完成。",
                )

        # 判断生成剧本意图（显式关键词）
        if stage in {"created", "script"} and (
            self._mentions_script_generation(text)
            or (self._has_generation_intent(text) and self._is_product_description(text))
        ):
            return self._plan(
                "GENERATE_SCRIPT",
                affected_stage="script",
                next_stage="script",
                assistant_content="我会开始生成剧本方案。",
            )

        # created 阶段：检测产品描述，自动生成剧本
        if stage == "created" and self._is_product_description(text):
            return self._plan(
                "GENERATE_SCRIPT",
                affected_stage="script",
                next_stage="script",
                assistant_content="我已了解您的产品需求，现在开始为您生成剧本方案。",
            )

        # 剧本阶段的其他文字输入视为剧本修改要求
        if stage == "script" and text:
            return self._plan(
                "UPDATE_SCRIPT_TEXT",
                affected_stage="script",
                next_stage="script",
                assistant_content="我会先记录你的剧本修改要求，并把后续图片和视频标记为需要更新。",
            )

        # created 阶段：普通对话（非产品描述）
        if stage == "created" and text:
            return self._plan(
                "CONVERSE",
                affected_stage="",
                assistant_content="你好，我在。你可以直接告诉我想做什么产品的带货视频，比如产品名称、卖点、风格或参考画面；我会先帮你整理剧本和分镜方向。",
            )

        # 无法判断意图时，返回澄清动作
        return self._plan(
            "ASK_CLARIFYING_QUESTION",
            affected_stage=stage,
            requires_confirmation=True,
            assistant_content="你想修改剧本、重生成某张图片，还是继续推进到下一阶段？",
        )

    def _plan(
        self,
        action: str,
        *,
        affected_stage: str,
        affected_frame_ids: list[int] | None = None,
        requires_confirmation: bool = False,
        assistant_content: str,
        next_stage: str | None = None,
    ) -> dict:
        """构造标准化的动作计划字典。"""
        return {
            "action": action,
            "affected_stage": affected_stage,
            "affected_frame_ids": affected_frame_ids or [],
            "requires_confirmation": requires_confirmation,
            "assistant_content": assistant_content,
            "next_stage": next_stage,
            "estimated_cost_label": "low" if action != "CONFIRM_IMAGES_AND_GENERATE_VIDEO" else "high",
        }

    def _resolve_frame_ids(self, frames: list, text: str, frame_id: int | None) -> list[int]:
        """从文本中解析帧序号（如"第2张"），或直接使用传入的 frame_id。"""
        if frame_id:
            return [frame_id]
        match = re.search(r"第\s*(\d+)\s*[张帧个]?", text)
        if not match:
            return []
        sequence = int(match.group(1))
        return [
            getattr(frame, "id")
            for frame in frames
            if getattr(frame, "sequence", None) == sequence and getattr(frame, "id", None) is not None
        ]

    def _has_confirm_intent(self, text: str) -> bool:
        """判断用户是否表达确认意图。"""
        return any(word in text for word in ("确认", "可以", "没问题", "下一步", "继续", "通过"))

    def _project_regeneration_action(self, text: str) -> str | None:
        """Detect project-level rerun modes from natural Chinese instructions."""
        if not any(word in text for word in ("重跑", "重做", "重新生成", "重生成", "重新来", "再生成")):
            return None

        if any(word in text for word in ("全部", "全流程", "从头", "从剧本", "剧本开始", "整个项目")):
            return "REGENERATE_PROJECT_ALL"

        keeps_script = any(word in text for word in ("剧本不变", "剧本和图片", "保留剧本", "脚本不变", "文案不变"))
        keeps_image = any(word in text for word in ("图片不变", "图片都不变", "图不变", "首帧不变", "保留图片", "保留首帧"))
        mentions_image = any(word in text for word in ("图片", "首帧", "画面"))
        mentions_video = any(word in text for word in ("视频", "成片", "片段"))

        if keeps_script and keeps_image:
            return "REGENERATE_VIDEO_ONLY"
        if keeps_script and mentions_image and mentions_video:
            return "REGENERATE_IMAGES_AND_VIDEO"
        if mentions_video and not mentions_image:
            return "REGENERATE_VIDEO_ONLY"

        return None

    def _mentions_image_or_next(self, text: str) -> bool:
        """判断用户是否提及图片或推进下一步。"""
        return any(word in text for word in ("图片", "这张图", "分镜图", "画面", "下一步", "继续"))

    def _mentions_video_or_next(self, text: str) -> bool:
        """判断用户是否提及视频或推进下一步。"""
        return any(word in text for word in ("视频", "成片", "下一步", "继续"))

    def _mentions_script_generation(self, text: str) -> bool:
        """判断用户是否要求生成剧本。"""
        return any(word in text for word in ("生成剧本", "开始剧本", "写剧本", "出脚本"))

    def _is_product_description(self, text: str) -> bool:
        """判断用户是否在描述产品或提供推广需求。"""
        if len(text) < 5:
            return False
        # 产品相关关键词
        product_keywords = [
            "产品", "推广", "卖", "推荐", "带货", "视频", "链接",
            "商品", "品牌", "价格", "优惠", "促销", "功能", "特点",
            "优势", "效果", "用户", "客户", "市场", "销售", "营销",
            "广告", "宣传", "介绍", "展示", "演示", "使用", "体验",
        ]
        # URL 模式
        url_pattern = r"https?://\S+"
        has_url = bool(re.search(url_pattern, text))
        has_keyword = any(kw in text for kw in product_keywords)
        has_generation_intent = self._has_generation_intent(text)
        has_video_or_sales_intent = any(word in text for word in ("带货", "视频", "商品", "产品", "推广", "广告"))
        # 有意义的长度 + 关键词或 URL
        return (len(text) >= 8 and has_generation_intent and has_video_or_sales_intent) or (len(text) > 10 and (has_keyword or has_url))

    def _has_generation_intent(self, text: str) -> bool:
        """判断用户是否明确要求生成或重新生成内容。"""
        return any(word in text for word in ("生成", "重新生成", "重生成", "制作", "做一个", "来一个", "写一个"))

    def _wants_image_regeneration(self, text: str, frame_ids: list[int]) -> bool:
        """判断用户是否要求重生成某张图片（需要同时有帧引用和图片相关词）。"""
        if not frame_ids:
            return False
        return any(word in text for word in ("图片", "这张图", "分镜图", "画面", "换成", "重生成", "不满意"))

    def _wants_change_bgm(self, text: str) -> bool:
        """判断用户是否要求更换背景音乐。"""
        return any(word in text for word in ("换一首", "换个BGM", "换音乐", "换个背景音乐", "换个bgm", "BGM换了", "bgm换了"))

    def _wants_tts_regeneration(self, text: str) -> bool:
        """判断用户是否要求重生成配音、旁白或调整音色。"""
        tts_keywords = ("配音", "旁白", "音色", "声音", "女声", "男声", "语速", "tts", "TTS")
        regenerate_keywords = ("重生成", "重新生成", "重做", "换", "调整", "修改")
        return any(word in text for word in tts_keywords) and any(word in text for word in regenerate_keywords)


workflow_agent_service = WorkflowAgentService()
