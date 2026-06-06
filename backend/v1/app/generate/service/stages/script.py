"""剧本生成服务"""
import json
import asyncio
import logging
import os
from typing import Optional
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.v1.app.models.project import Project
from backend.v1.app.models.frame import Frame
from backend.v1.app.models.script import Script
from backend.v1.app.generate.service.workflow import state as project_workflow_state
from backend.v1.app.generate.service.workflow.limits import normalize_target_duration
from backend.v1.app.push.model.message_model import PushMessage
from backend.providers import VolcanoLLM, ChatRequest, ChatMessage

logger = logging.getLogger(__name__)

# 场景类型映射：LLM 输出的字符串 -> 数据库存储的整数
SCENE_TYPE_MAP = {
    "hook": 0,
    "selling_point": 1,
    "detail": 2,
    "social_proof": 2,
    "price": 1,
    "cta": 4,
}

# ========== 资源文件加载 ==========
_RESOURCE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../../../../resources/template/resolve")
)
_PROMPT_DIR = os.path.join(_RESOURCE_DIR, "prompts")
_MOCK_SCENES_PATH = os.path.join(_RESOURCE_DIR, "valid_template", "script_mock_scenes.json")

_prompt_cache: dict[str, str] = {}


def _load_prompt(name: str) -> str:
    """从 prompts/ 目录加载 .txt 提示词文件（带缓存）"""
    if name in _prompt_cache:
        return _prompt_cache[name]
    path = os.path.join(_PROMPT_DIR, f"{name}.txt")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    _prompt_cache[name] = content
    return content


def _load_mock_scenes() -> list[dict]:
    """加载 Mock 场景配置 JSON"""
    with open(_MOCK_SCENES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


class ScriptGenerationService:
    """剧本生成服务（接入火山引擎 LLM）"""

    def __init__(self, rag_service=None):
        self._llm = None
        if rag_service is not None:
            self.rag_service = rag_service
        else:
            from backend.v1.app.search.rag_service_adapter import RAGServiceAdapter
            self.rag_service = RAGServiceAdapter()

    @property
    def llm(self):
        if self._llm is None:
            if VolcanoLLM is None:
                raise RuntimeError("VolcanoLLM 不可用，请安装 openai 依赖")
            self._llm = VolcanoLLM(key=None, model_name=None)
        return self._llm

    async def generate_script(
        self,
        db: AsyncSession,
        project_id: int,
        force: bool = False,
    ) -> list[Frame]:
        """
        生成带货剧本，逐帧写入 frames 表。
        target_duration 从 projects 表读取。
        """
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            raise ValueError(f"项目不存在: {project_id}")

        # 检查是否已有帧数据，避免重复生成
        existing_frames = await db.execute(
            select(Frame).where(Frame.project_id == project_id).order_by(Frame.sequence)
        )
        frames_list = existing_frames.scalars().all()
        if frames_list:
            logger.info(f"[剧本生成] 项目 {project_id} 已有 {len(frames_list)} 个帧，跳过生成")
            incomplete = any(
                frame.status == 3 or not frame.description or not frame.prompt
                for frame in frames_list
            )
            if not force and not incomplete:
                return frames_list

            active_task_result = await db.execute(
                select(PushMessage)
                .where(
                    PushMessage.message_type == "task_event",
                    PushMessage.project_id == project_id,
                    PushMessage.task_domain == "generation",
                    PushMessage.task_type.in_(["render", "frame_retry", "export"]),
                    PushMessage.status.in_(["queued", "running"]),
                )
                .limit(1)
            )
            if active_task_result.scalar_one_or_none():
                raise ValueError("项目正在渲染，不能删除分镜并重新生成剧本")

            logger.warning(
                f"[script_generation] project {project_id} regenerating script, "
                f"force={force}, incomplete={incomplete}"
            )
            for frame in frames_list:
                await db.delete(frame)
            await db.flush()

        # 限制总时长在 12-20 秒
        target_duration = normalize_target_duration(project.target_duration)

        # RAG 检索参考资料（带降级）
        rag_weight = float(project.rag_weight) if project.rag_weight else 0.3
        reference = await self._retrieve_references(project, rag_weight)

        # 构造 Prompt
        prompt = self._build_prompt(project, target_duration, reference)

        # 调用 LLM 生成剧本
        try:
            script_content = await self._call_llm(prompt)
            logger.info(f"[剧本生成] LLM 调用成功，project_id={project_id}")
        except Exception as e:
            logger.warning(f"[剧本生成] LLM 调用失败，使用 Mock 数据: {str(e)}")
            script_content = self._mock_generate(project, target_duration)

        script_version = await self._create_script_version(db, project, prompt, reference, script_content)

        # 逐场景写入 frames 表
        scenes = script_content.get("scenes", [])
        frames = []
        for index, scene in enumerate(scenes, 1):
            visual = scene.get("visual", {})
            overlay = visual.get("overlay", {})
            narration = scene.get("text", "")
            image_prompt = visual.get("image_prompt", narration)
            video_prompt = visual.get("video_prompt", "")
            subtitle_text = overlay.get("text", "")
            subtitle_position = overlay.get("position", "bottom")

            frame = Frame(
                project_id=project_id,
                script_id=script_version.id,
                sequence=index,
                scene_type=SCENE_TYPE_MAP.get(scene.get("type", ""), 0),
                description=image_prompt,
                prompt=video_prompt,
                narration=narration,
                subtitle_text=subtitle_text,
                subtitle_position=subtitle_position,
                image_prompt=image_prompt,
                video_prompt=video_prompt,
                text_overlay=subtitle_text,
                duration=max(1, scene.get("duration", 5)),
                transition_type=0,
                status=0,  # 待生成
                dirty=0,
                ai_params={
                    "camera": visual.get("camera", ""),
                    "mood": visual.get("mood", ""),
                    "overlay_position": subtitle_position,
                    "overlay_style": overlay.get("style", "highlight"),
                    "voice_style": scene.get("voice_style", ""),
                    "text": narration,
                },
                metadata_={
                    "source_scene_id": scene.get("scene_id"),
                    "scene_type_str": scene.get("type", ""),
                    "hook_line": script_content.get("video_meta", {}).get("hook_line", ""),
                },
            )
            db.add(frame)
            frames.append(frame)

        # 更新项目状态
        project_workflow_state.mark_project_stage_review(project, "script")
        await db.commit()

        # 刷新所有 frame 获取生成的 id
        for frame in frames:
            await db.refresh(frame)

        logger.info(f"[剧本生成] 已写入 {len(frames)} 个帧，project_id={project_id}")
        return frames

    async def _create_script_version(
        self,
        db: AsyncSession,
        project: Project,
        prompt: str,
        reference: str,
        script_content: dict,
    ) -> Script:
        result = await db.execute(
            select(func.coalesce(func.max(Script.version), 0)).where(Script.project_id == project.id)
        )
        next_version = int(result.scalar_one() or 0) + 1
        script = Script(
            project_id=project.id,
            version=next_version,
            status="active",
            generation_mode="llm",
            prompt_snapshot={
                "prompt": prompt,
                "title": project.title,
                "user_prompt": project.user_prompt,
                "target_duration": project.target_duration,
                "style": project.style,
                "target_audience": project.target_audience,
                "key_points": project.key_points,
                "avoid": project.avoid,
            },
            rag_snapshot={
                "rag_weight": float(project.rag_weight) if project.rag_weight else 0,
                "reference_text": reference,
            },
            content=script_content,
        )
        db.add(script)
        await db.flush()
        return script

    # ========== RAG 检索 ==========

    def _rag_top_k(self, rag_weight: float) -> int:
        """根据 rag_weight 映射 top_k"""
        if rag_weight <= 0:
            return 0
        if rag_weight <= 0.3:
            return 3
        if rag_weight <= 0.7:
            return 5
        return 10

    async def _retrieve_references(self, project: Project, rag_weight: float) -> str:
        """并行三路 RAG 检索，返回格式化的参考文本。
        同时将 RAG 检索到的图片 URL 存入 self.rag_image_urls 供下游图片生成使用。
        """
        self.rag_image_urls: list[str] = []

        if not self.rag_service:
            return ""
        top_k = self._rag_top_k(rag_weight)
        if top_k == 0:
            logger.info("[RAG] rag_weight=0，跳过检索")
            return ""

        query = project.user_prompt or project.title or ""
        ref_images = project.reference_images or []

        try:
            scripts, assets, knowledge = await asyncio.gather(
                self.rag_service.search_scripts(query, top_k=top_k),
                self.rag_service.search_assets(query, top_k=top_k, image_urls=ref_images),
                self.rag_service.search_product_knowledge(query, top_k=top_k),
                return_exceptions=True,
            )

            sections = []
            rag_detail = "摘要" if rag_weight <= 0.3 else ("关键内容" if rag_weight <= 0.7 else "完整内容")

            if isinstance(scripts, list) and scripts:
                sections.append(self._format_rag_section("参考剧本模板", scripts, rag_detail))
            elif isinstance(scripts, Exception):
                logger.warning(f"[RAG] 剧本检索异常: {scripts}")

            if isinstance(assets, list) and assets:
                sections.append(self._format_rag_section("参考视觉素材", assets, rag_detail))
                # 收集图片知识库中的图片 URL，供图片生成阶段使用
                for doc in assets:
                    if doc.url:
                        self.rag_image_urls.append(doc.url)
            elif isinstance(assets, Exception):
                logger.warning(f"[RAG] 素材检索异常: {assets}")

            if isinstance(knowledge, list) and knowledge:
                sections.append(self._format_rag_section("商品知识参考", knowledge, rag_detail))
            elif isinstance(knowledge, Exception):
                logger.warning(f"[RAG] 商品知识检索异常: {knowledge}")

            if self.rag_image_urls:
                logger.info(f"[RAG] 从图片知识库检索到 {len(self.rag_image_urls)} 张参考图")

            if not sections:
                return ""

            rag_header = _load_prompt("script_rag_header")
            return f"{rag_header}\n\n" + "\n\n".join(sections)

        except Exception as e:
            logger.warning(f"[RAG] 检索整体异常，降级为无参考模式: {e}")
            return ""

    def _format_rag_section(self, title: str, results: list, detail: str) -> str:
        """将 RAG 结果格式化为 prompt 参考区文本"""
        lines = [f"### {title}"]
        for i, r in enumerate(results, 1):
            if detail == "摘要":
                content = r.content[:50] + "..." if len(r.content) > 50 else r.content
            elif detail == "关键内容":
                content = r.content[:200] + "..." if len(r.content) > 200 else r.content
            else:
                content = r.content
            line = f"{i}. {content}"
            # 附带来源信息（标题、URL、图片URL等）
            meta_parts = []
            if r.title:
                meta_parts.append(f"标题: {r.title}")
            if r.url:
                meta_parts.append(f"参考图: {r.url}")
            if meta_parts:
                line += f" [{'，'.join(meta_parts)}]"
            lines.append(line)
        return "\n".join(lines)

    # ========== Prompt 组装 ==========

    def _format_product_info(self, product_info_json: str | None) -> str:
        """将 product_info JSON 格式化为可读文本"""
        if not product_info_json:
            return "- 商品详情：无"

        try:
            info = json.loads(product_info_json)
            parts = []
            if info.get("title"):
                parts.append(f"- 商品名称：{info['title']}")
            if info.get("price"):
                parts.append(f"- 价格：{info['price']}")
            if info.get("original_price"):
                parts.append(f"- 原价：{info['original_price']}")
            if info.get("description"):
                parts.append(f"- 商品描述：{info['description']}")
            if info.get("specs"):
                specs = info["specs"]
                if isinstance(specs, dict):
                    specs_text = "、".join(f"{k}:{v}" for k, v in specs.items())
                    parts.append(f"- 规格参数：{specs_text}")
            return "\n".join(parts) if parts else "- 商品详情：无"
        except (json.JSONDecodeError, TypeError):
            return f"- 商品详情：{product_info_json}"

    def _build_prompt(self, project: Project, target_duration: int, reference: str = "") -> str:
        """构造 LLM 生成 Prompt（分区加权结构）"""
        product_detail = self._format_product_info(project.product_info)

        # === 核心区：用户输入 + 商品信息（必须遵循） ===
        core_sections = []

        # 用户提示词（最高优先级）
        if project.user_prompt:
            tpl = _load_prompt("script_user_intent")
            core_sections.append(tpl.format(user_prompt=project.user_prompt))

        # 结构化字段
        structured = []
        if project.style:
            structured.append(f"- 视频风格：{project.style}")
        if project.target_audience:
            structured.append(f"- 目标受众：{project.target_audience}")
        if project.key_points:
            key_points = project.key_points
            if isinstance(key_points, list) and key_points:
                structured.append(f"- 重点强调：{', '.join(key_points)}")
        if project.avoid:
            avoid = project.avoid
            if isinstance(avoid, list) and avoid:
                structured.append(f"- 需要避免：{', '.join(avoid)}")
        if structured:
            tpl = _load_prompt("script_supplement")
            core_sections.append(tpl.format(structured_fields="\n".join(structured)))

        # 商品信息
        tpl = _load_prompt("script_product_info")
        core_sections.append(
            tpl.format(
                title=project.title,
                description=project.description or '无',
                product_detail=product_detail,
            )
        )

        # 参考图片
        ref_images = project.reference_images
        if ref_images and isinstance(ref_images, list) and ref_images:
            imgs_text = "\n".join(f"- {url}" for url in ref_images)
            tpl = _load_prompt("script_reference_images")
            core_sections.append(tpl.format(images_text=imgs_text))

        core_text = "\n\n".join(core_sections)

        # === 组装完整 prompt ===
        template = _load_prompt("script_generation")
        prompt = template.format(
            target_duration=target_duration,
            core_sections=core_text,
            reference=reference or "",
        )

        return prompt

    # ========== LLM 调用 ==========

    async def _call_llm(self, prompt: str) -> dict:
        """调用 LLM 生成剧本"""
        system_prompt = _load_prompt("script_system")
        request = ChatRequest(
            messages=[
                ChatMessage(role="system", content=system_prompt),
                ChatMessage(role="user", content=prompt),
            ],
            temperature=0.7,
            max_tokens=4096,
        )

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, self.llm.chat, request)

        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        script_content = json.loads(content.strip())

        required_fields = ["video_meta", "scenes", "audio"]
        for field in required_fields:
            if field not in script_content:
                raise ValueError(f"LLM 返回的 JSON 缺少必要字段: {field}")

        for scene in script_content.get("scenes", []):
            visual = scene.get("visual", {})
            if "image_prompt" not in visual:
                logger.warning(f"场景 {scene.get('scene_id')} 缺少 image_prompt，使用 text 作为 fallback")
                visual["image_prompt"] = scene.get("text", "")
            if "video_prompt" not in visual:
                logger.warning(f"场景 {scene.get('scene_id')} 缺少 video_prompt，使用 image_prompt 作为 fallback")
                visual["video_prompt"] = visual.get("image_prompt", "")

        return script_content

    def _mock_generate(self, project: Project, target_duration: int) -> dict:
        """Mock 剧本生成（作为 LLM 调用失败的 fallback）"""
        scene_configs = _load_mock_scenes()
        scenes = []
        total_sec = 0

        for i, config in enumerate(scene_configs):
            remaining = target_duration - total_sec
            if remaining < 4:
                break
            duration = min(8, remaining)
            overlay = config["overlay"].copy()
            if "{title}" in overlay.get("text", ""):
                overlay["text"] = overlay["text"].replace("{title}", project.title)
            scenes.append({
                "scene_id": i + 1,
                "type": config["type"],
                "duration": duration,
                "text": f"{project.title}的第{i+1}个卖点，详细讲解产品优势和使用场景。",
                "voice_style": config["voice_style"],
                "visual": {
                    "image_prompt": config["image_prompt"],
                    "video_prompt": config["video_prompt"],
                    "camera": "push_in" if i % 2 == 0 else "pan_left",
                    "mood": "warm",
                    "overlay": overlay,
                },
            })
            total_sec += duration

        return {
            "video_meta": {
                "product_name": project.title,
                "target_duration": target_duration,
                "style": "lifestyle",
                "aspect_ratio": "9:16",
                "hook_line": f"还在为选{project.title}发愁？",
            },
            "scenes": scenes,
            "audio": {
                "tts_voice": "zh_female_cancan_mars_bigtts",
                "bgm": "轻松愉快的吉他弹唱背景音乐",
                "bgm_volume": 0.3,
            },
        }


script_generation_service = ScriptGenerationService()
