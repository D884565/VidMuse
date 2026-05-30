"""剧本生成服务"""
import json
import asyncio
import logging
from typing import Optional
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.v1.app.models.project import Project
from backend.v1.app.models.frame import Frame
from backend.v1.app.models.generation_task import GenerationTask
from backend.v1.app.models.script import Script
from backend.v1.app.generate.service import project_workflow_state
from backend.providers import VolcanoLLM, ChatRequest, ChatMessage
from backend.v1.app.generate.service._rag_temp.rag_service import (
    RAGService, MockRAGService, RAGResult,
)

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


class ScriptGenerationService:
    """剧本生成服务（接入火山引擎 LLM + RAG 检索）"""

    def __init__(self, rag_service: Optional[RAGService] = None):
        """初始化 LLM 客户端和 RAG 服务"""
        self.llm = VolcanoLLM(key=None, model_name=None)
        self.rag_service: RAGService = rag_service or MockRAGService()

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
                select(GenerationTask)
                .where(
                    GenerationTask.project_id == project_id,
                    GenerationTask.task_type.in_(["render", "frame_retry", "export"]),
                    GenerationTask.status.in_(["queued", "running"]),
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
        target_duration = max(12, min(20, project.target_duration or 15))

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
                duration=scene.get("duration", 3),
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
        """并行三路 RAG 检索，返回格式化的参考文本"""
        top_k = self._rag_top_k(rag_weight)
        if top_k == 0:
            logger.info("[RAG] rag_weight=0，跳过检索")
            return ""

        query = project.user_prompt or project.title or ""
        image_url = (project.reference_images or [None])[0] if project.reference_images else None

        try:
            scripts, assets, knowledge = await asyncio.gather(
                self.rag_service.search_scripts(query, top_k=top_k),
                self.rag_service.search_assets(query, image_url=image_url, top_k=top_k),
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
            elif isinstance(assets, Exception):
                logger.warning(f"[RAG] 素材检索异常: {assets}")

            if isinstance(knowledge, list) and knowledge:
                sections.append(self._format_rag_section("商品知识参考", knowledge, rag_detail))
            elif isinstance(knowledge, Exception):
                logger.warning(f"[RAG] 商品知识检索异常: {knowledge}")

            if not sections:
                return ""

            return "## 参考资料（仅供参考借鉴，不要照搬）\n\n" + "\n\n".join(sections)

        except Exception as e:
            logger.warning(f"[RAG] 检索整体异常，降级为无参考模式: {e}")
            return ""

    def _format_rag_section(self, title: str, results: list[RAGResult], detail: str) -> str:
        """将 RAG 结果格式化为 prompt 参考区文本"""
        lines = [f"### {title}"]
        for i, r in enumerate(results, 1):
            if detail == "摘要":
                content = r.content[:50] + "..." if len(r.content) > 50 else r.content
            elif detail == "关键内容":
                content = r.content[:200] + "..." if len(r.content) > 200 else r.content
            else:
                content = r.content
            lines.append(f"{i}. {content}")
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
            core_sections.append(f"## 用户创作意图（必须严格遵循）\n{project.user_prompt}")

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
            core_sections.append("## 补充要求\n" + "\n".join(structured))

        # 商品信息
        core_sections.append(
            f"## 商品信息\n"
            f"- 商品标题：{project.title}\n"
            f"- 商品描述：{project.description or '无'}\n"
            f"{product_detail}"
        )

        # 参考图片
        ref_images = project.reference_images
        if ref_images and isinstance(ref_images, list) and ref_images:
            imgs_text = "\n".join(f"- {url}" for url in ref_images)
            core_sections.append(f"## 用户提供的参考图片\n{imgs_text}")

        core_text = "\n\n".join(core_sections)

        # === 组装完整 prompt ===
        prompt_parts = [
            f"你是一个专业的带货视频编剧，擅长创作短视频带货剧本。请根据以下信息，生成一个约{target_duration}秒的带货短视频剧本。\n",
            core_text,
        ]

        # 参考区（仅在有内容时添加）
        if reference:
            prompt_parts.append(reference)

        # 输出格式约束
        prompt_parts.append(self._output_format_section(target_duration))

        return "\n\n".join(prompt_parts)

    def _output_format_section(self, target_duration: int) -> str:
        """输出格式约束"""
        return (
            f"## 输出要求\n"
            f"请严格按照以下 JSON 格式输出，不要输出其他内容：\n"
            f"```json\n"
            f'{{\n'
            f'  "video_meta": {{\n'
            f'    "product_name": "商品名称",\n'
            f'    "target_duration": {target_duration},\n'
            f'    "style": "视频风格(fashion/tech/food/lifestyle)",\n'
            f'    "aspect_ratio": "9:16",\n'
            f'    "hook_line": "一句话开场金句，用于封面或字幕"\n'
            f'  }},\n'
            f'  "scenes": [\n'
            f'    {{\n'
            f'      "scene_id": 1,\n'
            f'      "type": "hook",\n'
            f'      "duration": 5,\n'
            f'      "text": "配音文案（口语化，有感染力）",\n'
            f'      "voice_style": "excited",\n'
            f'      "visual": {{\n'
            f'        "image_prompt": "图片生成提示词：详细描述画面内容，包括主体、背景、光线、色调、构图",\n'
            f'        "video_prompt": "视频生成提示词：描述镜头运动和动态效果",\n'
            f'        "camera": "镜头运动方式（push_in/pull_out/pan_left/pan_right/static/close_up/wide_shot）",\n'
            f'        "mood": "画面氛围（warm/bright/dark/energetic/elegant）",\n'
            f'        "overlay": {{\n'
            f'          "text": "画面上叠加的关键文字，不超过10个字，不需要时留空",\n'
            f'          "position": "文字位置（top/center/bottom）",\n'
            f'          "style": "文字风格（highlight/price_tag/call_to_action/subtle）"\n'
            f'        }}\n'
            f'      }}\n'
            f'    }}\n'
            f'  ],\n'
            f'  "audio": {{\n'
            f'    "tts_voice": "zh_female_cancan_mars_bigtts",\n'
            f'    "bgm": "背景音乐风格描述",\n'
            f'    "bgm_volume": 0.3\n'
            f'  }}\n'
            f'}}\n'
            f'```\n\n'
            f"## 场景类型说明\n"
            f"- hook: 开场，前3秒抓住注意力（3-5秒）\n"
            f"- selling_point: 卖点展示（4-8秒）\n"
            f"- detail: 细节特写（3-6秒）\n"
            f"- social_proof: 口碑背书（3-5秒）\n"
            f"- price: 价格优惠（3-5秒）\n"
            f"- cta: 行动号召（3-5秒）\n\n"
            f"## 注意事项\n"
            f"1. 总时长 12-20 秒，scenes 3-5 个，每个场景 3-8 秒\n"
            f"2. image_prompt 要详细（主体、背景、光线、色调、构图）\n"
            f"3. video_prompt 要描述镜头运动和画面变化\n"
            f"4. 文案口语化、有感染力，适合短视频带货\n"
            f"5. voice_style 可选：excited/confident/urgent/warm/professional\n"
            f"6. 前3秒是黄金时间，hook 必须足够吸引人\n"
            f"7. overlay.text 简短有力，不超过10个字"
        )

    # ========== LLM 调用 ==========

    async def _call_llm(self, prompt: str) -> dict:
        """调用 LLM 生成剧本"""
        request = ChatRequest(
            messages=[
                ChatMessage(role="system", content=(
                    "你是一个专业的带货视频编剧，擅长创作短视频剧本。\n"
                    "你的输出必须是严格的 JSON 格式，不要包含任何其他文字。\n"
                    "image_prompt 要详细描述画面（主体、背景、光线、色调），用于 AI 图片生成。\n"
                    "video_prompt 要描述镜头运动和动态效果，用于 AI 视频生成。\n"
                    "overlay 用于指定画面上叠加的关键文字，简短有力，不超过10个字，用于提高转化率。"
                )),
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
        scenes = []
        total_sec = 0
        scene_configs = [
            ("hook", "excited", "一位年轻女性手持木吉他坐在窗边，温暖的阳光洒在吉他面板上，背景是简约的白色墙壁，暖色调，竖屏构图",
             "镜头从吉他全景缓慢推近至面板特写，阳光光斑微微晃动",
             {"text": project.title, "position": "bottom", "style": "highlight"}),
            ("selling_point", "confident", "吉他面板木纹特写，云杉木纹理清晰可见，浅景深，柔和的侧光照明，专业产品摄影风格",
             "镜头从左向右缓慢平移，展示木纹质感，微距效果",
             {"text": "云杉木面板", "position": "bottom", "style": "highlight"}),
            ("detail", "professional", "吉他弦钮和琴头特写，金属弦钮反射光线，背景虚化，高端产品摄影风格",
             "镜头环绕琴头旋转，弦钮金属光泽闪烁",
             {"text": "好评率98%", "position": "top", "style": "subtle"}),
            ("price", "urgent", "吉他搭配全套配件展示：调音器、琴包、拨片、备用琴弦，整齐摆放在桌面上，促销氛围灯光",
             "镜头从配件全景快速推近至价格标签，动感效果",
             {"text": "限时特惠 ¥649", "position": "center", "style": "price_tag"}),
            ("cta", "warm", "女性微笑弹奏吉他，自然光，温馨的家庭环境，竖屏构图，幸福感氛围",
             "镜头缓慢拉远，展示完整弹奏画面，温暖色调",
             {"text": "点击下单", "position": "bottom", "style": "call_to_action"}),
        ]

        for i, (scene_type, voice, img_prompt, vid_prompt, overlay) in enumerate(scene_configs):
            duration = min(8, target_duration - total_sec)
            if duration <= 2:
                break
            scenes.append({
                "scene_id": i + 1,
                "type": scene_type,
                "duration": duration,
                "text": f"{project.title}的第{i+1}个卖点，详细讲解产品优势和使用场景。",
                "voice_style": voice,
                "visual": {
                    "image_prompt": img_prompt,
                    "video_prompt": vid_prompt,
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
