"""剧本生成服务"""
import json
import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import func, select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.v1.app.models.project import Project
from backend.v1.app.models.frame import Frame
from backend.v1.app.models.generation_task import GenerationTask
from backend.v1.app.models.script import Script
from backend.v1.app.models.asset import Asset
from backend.v1.app.models.project_asset import ProjectAsset
from backend.v1.app.generate.service.chat.material_resolver import MaterialResolver
from backend.v1.app.generate.service.workflow import state as project_workflow_state
from backend.v1.app.generate.service.workflow.limits import normalize_target_duration
from backend.v1.app.script.service.template_script_service import template_script_service
from backend.v1.app.generate.service.chat.parsed_material_prompt import format_material_prompt_section
# 导入移到属性内部，避免循环导入
# from backend.v1.app.agent import ScriptAgent

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
    """剧本生成服务（接入Agent架构）"""

    def __init__(self):
        self._script_agent = None


    @property
    def script_agent(self):
        if self._script_agent is None:
            try:
                # 动态导入避免循环依赖
                from backend.v1.app.agent.implementations.script_agent import ScriptAgent
                self._script_agent = ScriptAgent()
            except Exception as e:
                raise RuntimeError(f"初始化ScriptAgent失败: {str(e)}")
        return self._script_agent

    async def generate_script(
        self,
        db: AsyncSession,
        project_id: int,
        force: bool = False,
        template_id: str | None = None,
        template_params: dict | None = None,
        creation_mode: str | None = None,
        strategy_id: str | None = None,
        local_references: list | None = None,
    ) -> list[Frame]:
        """
        生成带货剧本，逐帧写入 frames 表。
        target_duration 从 projects 表读取。
        :param creation_mode: 创作模式：independent(自主创作，默认)/auto/hot_video/template/strategy
        :param strategy_id: 指定使用的策略ID，仅在strategy模式下有效
        :param local_references: 本地参考素材列表（图片features/文本content）
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
        target_duration = normalize_target_duration(project.target_duration)


        # 构造 Prompt
        strategy = None
        used_factors = None
        if template_id:
            # 调用模板服务处理模板数据
            template_data = await template_script_service.process_template_data(db, template_id, template_params)
            template = template_data["template"]
            if template:
                strategy = template_data["strategy"]
                used_factors = template_data["used_factors"]
                # 基于模板构建prompt
                base_prompt = await self._build_prompt(db, project, target_duration)
                prompt = template_script_service.build_prompt_with_template(base_prompt, template, template_params)
            else:
                logger.warning(f"模板ID {template_id} 不存在，使用默认生成方式")
                prompt = await self._build_prompt(db, project, target_duration)
        else:
            prompt = await self._build_prompt(db, project, target_duration)

        # 构建素材参考内容
        material_reference = await self._build_material_reference(db, project_id)
        local_reference_text = self._build_local_reference_text(local_references)

        # 将聊天上传的图片和素材库资产的图片同步到 project.reference_images
        await self._sync_reference_images(db, project, local_references)

        # 调用 Agent 生成剧本
        try:
            script_content = await self._call_agent(
                db,
                prompt,
                project,
                target_duration,
                creation_mode=creation_mode,
                template_id=template_id,
                strategy_id=strategy_id,
                template_params=template_params,
                material_reference=material_reference,
                local_reference_text=local_reference_text,
            )
            logger.info(f"[剧本生成] Agent 调用成功，project_id={project_id}, mode={creation_mode}")
        except Exception as e:
            logger.warning(f"[剧本生成] Agent 调用失败，使用 Mock 数据: {str(e)}")
            script_content = self._mock_generate(project, target_duration)

        # 获取策略ID
        strategy_id = strategy.get('strategy_id') if strategy else None

        script_version = await self._create_script_version(
            db,
            project,
            prompt,
            script_content,
            template_id=template_id,
            strategy_id=strategy_id,
            used_factors=used_factors,
            template_params=template_params,
            creation_mode=creation_mode,
        )

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

    async def revise_script(
        self,
        db: AsyncSession,
        project_id: int,
        revision_instruction: str,
        script_id: Optional[int] = None,
        current_script: Optional[Dict[str, Any]] = None,
        modification_history: Optional[List[Dict[str, Any]]] = None,
        force_regenerate_frames: bool = True
    ) -> Dict[str, Any]:
        """
        修改已有剧本
        :param db: 数据库会话
        :param project_id: 项目ID
        :param revision_instruction: 修改指令
        :param script_id: 要修改的剧本ID，不传则使用当前项目最新的激活版本
        :param current_script: 直接传入当前剧本内容（可选，优先级高于script_id）
        :param modification_history: 历史修改记录（可选，用于多轮修改）
        :param force_regenerate_frames: 是否重新生成frames表数据，默认True
        :return: 修改结果，包含新的剧本和帧信息
        """
        from backend.v1.app.models.project import Project
        from backend.v1.app.models.script import Script
        from backend.v1.app.models.frame import Frame

        # 验证项目存在
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            raise ValueError(f"项目不存在: {project_id}")

        # 获取当前剧本内容
        script_data = None
        original_script = None

        if current_script:
            script_data = current_script
        else:
            # 根据script_id或项目ID查询剧本
            if script_id:
                result = await db.execute(select(Script).where(Script.id == script_id))
                original_script = result.scalar_one_or_none()
                if not original_script or original_script.project_id != project_id:
                    raise ValueError(f"剧本不存在或不属于当前项目: {script_id}")
            else:
                # 查询项目最新的激活版本
                result = await db.execute(
                    select(Script)
                    .where(Script.project_id == project_id, Script.status == "active")
                    .order_by(Script.version.desc())
                    .limit(1)
                )
                original_script = result.scalar_one_or_none()
                if not original_script:
                    raise ValueError(f"项目 {project_id} 没有可用的剧本版本")

            script_data = original_script.content

        if not script_data:
            raise ValueError("剧本内容为空，无法修改")

        try:
            # 调用Agent修改剧本
            loop = asyncio.get_event_loop()
            revised_script = await loop.run_in_executor(
                None,
                lambda: asyncio.run(
                    self.script_agent.revise_script(
                        current_script=script_data,
                        revision_instruction=revision_instruction,
                        modification_history=modification_history
                    )
                )
            )

            # 提取修改说明
            modification_note = revised_script.pop("modification_note", "已完成剧本修改")

            # 创建新版本剧本
            next_version = 1
            if original_script:
                next_version = original_script.version + 1

            # 确定生成模式
            generation_mode = "revision"

            # 构建修改历史
            new_modification_history = modification_history or []
            new_modification_history.append({
                "instruction": revision_instruction,
                "note": modification_note,
                "timestamp": datetime.now().isoformat()
            })

            # 创建新版本剧本记录
            new_script = Script(
                project_id=project_id,
                version=next_version,
                status="active",
                generation_mode=generation_mode,
                template_id=original_script.template_id if original_script else None,
                strategy_id=original_script.strategy_id if original_script else None,
                used_factors=original_script.used_factors if original_script else None,
                template_params=original_script.template_params if original_script else None,
                parent_id=original_script.id if original_script else None,  # 记录父版本
                prompt_snapshot={
                    **(original_script.prompt_snapshot if original_script else {}),
                    "revision_instruction": revision_instruction,
                    "modification_history": new_modification_history
                },
                rag_snapshot={},
                content=revised_script,
                # modification_history存储在prompt_snapshot中，兼容现有表结构
            )
            db.add(new_script)
            await db.flush()

            frames = []
            if force_regenerate_frames:
                # 删除原有帧数据
                await db.execute(delete(Frame).where(Frame.project_id == project_id))
                await db.flush()

                # 重新生成帧数据，复用原有逻辑
                scenes = revised_script.get("scenes", [])
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
                        script_id=new_script.id,
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
                            "hook_line": revised_script.get("video_meta", {}).get("hook_line", ""),
                            "modification_note": modification_note
                        },
                    )
                    db.add(frame)
                    frames.append(frame)

            project.video_output_url = None
            project.audio_url = None
            project_workflow_state.invalidate_project_from(project, "script")
            project_workflow_state.mark_project_stage_review(project, "script")
            await db.commit()

            # 刷新数据
            await db.refresh(new_script)
            for frame in frames:
                await db.refresh(frame)

            logger.info(f"[剧本修改] 成功，project_id={project_id}, 新版本号={next_version}")

            return {
                "success": True,
                "script_id": new_script.id,
                "version": next_version,
                "modification_note": modification_note,
                "script_content": revised_script,
                "frames": frames,
                "frame_count": len(frames),
                "modification_history": new_modification_history
            }

        except Exception as e:
            logger.error(f"[剧本修改] 失败: {str(e)}", exc_info=True)
            raise RuntimeError(f"剧本修改失败: {str(e)}")

    async def _create_script_version(
        self,
        db: AsyncSession,
        project: Project,
        prompt: str,
        script_content: dict,
        template_id: str | None = None,
        strategy_id: str | None = None,
        used_factors: list | dict | None = None,
        template_params: dict | None = None,
        creation_mode: str | None = None,
    ) -> Script:
        result = await db.execute(
            select(func.coalesce(func.max(Script.version), 0)).where(Script.project_id == project.id)
        )
        next_version = int(result.scalar_one() or 0) + 1

        # 确定生成模式
        generation_mode = "template" if template_id else "llm"

        script = Script(
            project_id=project.id,
            version=next_version,
            status="active",
            generation_mode=generation_mode,
            template_id=template_id,
            strategy_id=strategy_id,
            used_factors=used_factors,
            template_params=template_params,
            prompt_snapshot={
                "prompt": prompt,
                "title": project.title,
                "user_prompt": project.user_prompt,
                "target_duration": project.target_duration,
                "style": project.style,
                "target_audience": project.target_audience,
                "key_points": project.key_points,
                "avoid": project.avoid,
                "creation_mode": creation_mode,
                "template_id": template_id,
                "strategy_id": strategy_id,
                "template_params": template_params
            },
            rag_snapshot={},  # 保留字段，兼容数据库结构
            content=script_content,
        )
        db.add(script)
        await db.flush()

        # 如果使用了模板，增加模板的使用次数
        if template_id:
            await template_script_service.increment_template_usage(db, template_id)

        return script


    # ========== 素材参考构建 ==========

    async def _build_material_reference(self, db: AsyncSession, project_id: int) -> str:
        """从 ProjectAsset 关联表读取素材库解析内容，格式化为参考文本。"""
        result = await db.execute(
            select(Asset)
            .join(ProjectAsset, ProjectAsset.asset_id == Asset.id)
            .where(ProjectAsset.project_id == project_id)
            .order_by(ProjectAsset.id.asc())
        )
        materials = []
        for asset in result.scalars().all():
            ai_features = asset.ai_features or {}
            reference_text = MaterialResolver._build_reference_text(ai_features)
            if not reference_text:
                continue
            materials.append({
                "title": asset.title or f"Asset {asset.id}",
                "prompt_summary": {"reference_text": reference_text},
            })
        return format_material_prompt_section(materials)

    @staticmethod
    def _build_local_reference_text(local_references: list | None) -> str:
        """从 local_references 列表构建本地参考文本。"""
        if not local_references:
            return ""
        parts = []
        for ref in local_references:
            if not ref:
                continue
            ref_type = ref.get("type")
            if ref_type == "image":
                features = ref.get("features") or {}
                ref_text = features.get("reference_text", "")
                title = ref.get("title", "参考图")
                if ref_text:
                    parts.append(f"本地参考图片（{title}）：\n{ref_text}")
            elif ref_type == "text":
                content = ref.get("content", "")
                if content:
                    parts.append(f"本地参考文本：\n{content}")
        if not parts:
            return ""
        return "本地参考素材：\n\n" + "\n\n".join(parts)

    @staticmethod
    async def _sync_reference_images(
        db: AsyncSession,
        project: Project,
        local_references: list | None = None,
    ) -> None:
        """将聊天上传的图片和素材库资产的图片同步到 project.reference_images。

        这样图片生成阶段的 extract_reference_images() 就能读到这些图片。
        只追加新 URL，不覆盖已有的。
        """
        existing: list[str] = project.reference_images or []
        if not isinstance(existing, list):
            existing = []
        seen = set(existing)
        added = []

        # 1. 从 local_references 中提取聊天上传的图片 URL
        for ref in local_references or []:
            if not isinstance(ref, dict):
                continue
            if ref.get("type") != "image":
                continue
            url = ref.get("url")
            if url and isinstance(url, str) and url.strip() and url not in seen:
                added.append(url.strip())
                seen.add(url)

        # 2. 从素材库资产中提取图片 URL（ProjectAsset role=reference）
        result = await db.execute(
            select(Asset.url)
            .join(ProjectAsset, ProjectAsset.asset_id == Asset.id)
            .where(
                ProjectAsset.project_id == project.id,
                Asset.type == 1,  # 图片类型
                Asset.url.isnot(None),
            )
        )
        for (url,) in result.all():
            if url and isinstance(url, str) and url.strip() and url not in seen:
                added.append(url.strip())
                seen.add(url)

        if added:
            project.reference_images = existing + added
            await db.flush()
            logger.info(
                f"[剧本生成] 同步 {len(added)} 张参考图到 project.reference_images, "
                f"project_id={project.id}"
            )

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
            # 从ai_features中获取规格参数，兼容旧格式
            specs = info.get("specs") or info.get("ai_features", {}).get("parameters", {})
            if specs and isinstance(specs, dict):
                specs_text = "、".join(f"{k}:{v}" for k, v in specs.items())
                parts.append(f"- 规格参数：{specs_text}")
            return "\n".join(parts) if parts else "- 商品详情：无"
        except (json.JSONDecodeError, TypeError):
            return f"- 商品详情：{product_info_json}"

    async def _format_product_from_db(self, db: AsyncSession, product_id: int) -> str:
        """从 Product 表读取完整商品信息，格式化为可读文本。"""
        from backend.v1.app.models.product import Product
        from backend.v1.app.product.dao.schema import _parse_json_field

        result = await db.execute(select(Product).where(Product.id == product_id))
        product = result.scalar_one_or_none()
        if not product:
            return ""

        parts = []
        if product.name:
            parts.append(f"- 商品名称：{product.name}")
        if product.brand:
            parts.append(f"- 品牌：{product.brand}")
        if product.category:
            parts.append(f"- 商品分类：{product.category}")
        if product.description:
            parts.append(f"- 商品描述：{product.description}")
        if product.price is not None:
            parts.append(f"- 价格：{product.price}元")
        selling_points = _parse_json_field(product.selling_points, [])
        if selling_points:
            parts.append(f"- 卖点：{'、'.join(selling_points)}")
        specs = _parse_json_field(getattr(product, 'specs', None), {})
        if specs:
            specs_text = "、".join(f"{k}:{v}" for k, v in specs.items())
            parts.append(f"- 规格参数：{specs_text}")
        tags = _parse_json_field(getattr(product, 'tags', None), [])
        if tags:
            parts.append(f"- 标签：{'、'.join(tags)}")
        # 从 ai_features 中提取解析结果
        ai_features = product.ai_features or {}
        if isinstance(ai_features, dict):
            basic_info = ai_features.get("basic_info", {})
            if isinstance(basic_info, dict):
                if basic_info.get("target_audience"):
                    parts.append(f"- 目标人群：{basic_info['target_audience']}")
                if basic_info.get("scenarios"):
                    scenarios = basic_info["scenarios"]
                    if isinstance(scenarios, list):
                        parts.append(f"- 使用场景：{'、'.join(str(s) for s in scenarios)}")
            ai_selling = ai_features.get("selling_points", [])
            if ai_selling and isinstance(ai_selling, list):
                parts.append(f"- AI提炼卖点：{'、'.join(str(s) for s in ai_selling)}")

        return "\n".join(parts) if parts else ""

    async def _build_prompt(self, db: AsyncSession, project: Project, target_duration: int) -> str:
        """构造 LLM 生成 Prompt（分区加权结构）"""
        product_detail = self._format_product_info(project.product_info)
        # 如果项目关联了商品，从 Product 表读取完整信息补充到商品详情
        if project.product_id:
            db_product_info = await self._format_product_from_db(db, project.product_id)
            if db_product_info:
                product_detail = db_product_info

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
            f"你是一个专业的带货视频编剧，擅长创作短视频带货剧本。"
            f"请根据以下信息，生成一个约 {target_duration} 秒的带货短视频剧本。"
            f"共 3-5 个场景，每个场景 3-8 秒。\n",
            core_text,
        ]

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

    # ========== Agent 调用 ==========

    async def _call_agent(
        self,
        db: AsyncSession,
        prompt: str,
        project: Project,
        target_duration: int,
        creation_mode: Optional[str] = None,
        template_id: Optional[str] = None,
        strategy_id: Optional[str] = None,
        template_params: Optional[Dict[str, Any]] = None,
        material_reference: str = "",
        local_reference_text: str = "",
    ) -> dict:
        """调用 ScriptAgent 生成剧本"""
        # 提取项目信息
        product_detail = self._format_product_info(project.product_info)
        # 如果项目关联了商品，从 Product 表读取完整信息补充到商品详情
        if project.product_id:
            db_product_info = await self._format_product_from_db(db, project.product_id)
            if db_product_info:
                product_detail = db_product_info

        project_info = {
            "商品标题": project.title,
            "商品描述": project.description or "无",
            "商品详情": product_detail,
            "用户创作意图": project.user_prompt or "",
            "视频风格": project.style or "",
            "目标受众": project.target_audience or "",
            "重点强调": ", ".join(project.key_points) if isinstance(project.key_points, list) and project.key_points else "",
            "需要避免": ", ".join(project.avoid) if isinstance(project.avoid, list) and project.avoid else "",
            "参考图片": "\n".join(f"- {url}" for url in project.reference_images) if isinstance(project.reference_images, list) and project.reference_images else "",
            "商品分类": getattr(project, "category", "") or "",
        }

        # 注入素材库解析内容
        if material_reference:
            project_info["素材分析参考"] = material_reference

        # 注入本地参考素材
        if local_reference_text:
            project_info["本地参考素材"] = local_reference_text

        # 过滤空值
        project_info = {k: v for k, v in project_info.items() if v}

        # 获取输出格式要求
        output_format = self._output_format_section(target_duration)

        # 确定创作模式
        # 如果用户指定了template_id但没指定模式，默认使用template模式
        if template_id and not creation_mode:
            creation_mode = "template"
        # 如果没有指定模式，默认使用auto模式，由大模型自主选择最合适的创作模式
        elif not creation_mode:
            creation_mode = "auto"

        try:
            # 在独立线程中运行Agent（避免阻塞事件循环）
            trace_context = {
                "session_id": f"script_project_{getattr(project, 'id', 'unknown')}",
                "project_id": getattr(project, "id", None),
                "user_id": getattr(project, "user_id", None),
                "meta_data": {
                    "source": "script_generation_service",
                    "creation_mode": creation_mode,
                    "template_id": template_id,
                    "strategy_id": strategy_id,
                },
            }
            loop = asyncio.get_event_loop()
            script_content = await loop.run_in_executor(
                None,
                lambda: asyncio.run(
                    self.script_agent.generate_script(
                        project_info=project_info,
                        target_duration=target_duration,
                        output_format=output_format,
                        creation_mode=creation_mode,
                        template_id=template_id,
                        strategy_id=strategy_id,
                        template_params=template_params,
                        context=trace_context
                    )
                )
            )

            # 兼容 Agent 返回的格式变体
            script_content = self._normalize_agent_output(script_content, project, target_duration)

            # 规则层硬约束校验
            auto_fixed, warnings = self._validate_script_constraints(script_content, target_duration)
            if auto_fixed:
                logger.info(f"[剧本生成] 规则层自动修复: {auto_fixed}")
            if warnings:
                logger.warning(f"[剧本生成] 规则层警告: {warnings}")
                script_content["_warnings"] = warnings

            for scene in script_content.get("scenes", []):
                visual = scene.get("visual", {})
                if "image_prompt" not in visual:
                    logger.warning(f"场景 {scene.get('scene_id')} 缺少 image_prompt，使用 text 作为 fallback")
                    visual["image_prompt"] = scene.get("text", "")
                if "video_prompt" not in visual:
                    logger.warning(f"场景 {scene.get('scene_id')} 缺少 video_prompt，使用 image_prompt 作为 fallback")
                    visual["video_prompt"] = visual.get("image_prompt", "")

            return script_content

        except Exception as e:
            logger.error(f"调用Agent生成剧本失败: {str(e)}", exc_info=True)
            raise

    @staticmethod
    def _normalize_agent_output(raw: dict, project: Project, target_duration: int) -> dict:
        """将 Agent 返回的各种格式统一为标准格式 {video_meta, scenes, audio}。"""
        if not isinstance(raw, dict):
            raise ValueError(f"Agent 返回非 dict 类型: {type(raw)}")

        has_video_meta = "video_meta" in raw
        has_scenes = "scenes" in raw
        has_audio = "audio" in raw

        # 已经是标准格式
        if has_video_meta and has_scenes and has_audio:
            pass
        elif has_scenes:
            if not has_video_meta:
                raw["video_meta"] = {
                    "product_name": project.title,
                    "target_duration": raw.get("total_duration", target_duration),
                    "style": "lifestyle",
                    "aspect_ratio": "9:16",
                    "hook_line": "",
                }
            if not has_audio:
                raw["audio"] = {
                    "tts_voice": "zh_female_cancan_mars_bigtts",
                    "bgm": "轻松愉快的背景音乐",
                    "bgm_volume": 0.3,
                }
            logger.warning("[剧本生成] Agent 返回格式缺少字段，已自动补全")
        else:
            raise ValueError(f"Agent 返回的 JSON 缺少 scenes 字段: {list(raw.keys())}")

        # 校验并截断总时长
        scenes = raw.get("scenes", [])
        total = sum(float(s.get("duration", 0)) for s in scenes)
        if total > target_duration and scenes:
            overflow = total - target_duration
            for scene in reversed(scenes):
                dur = float(scene.get("duration", 0))
                cut = min(overflow, dur - 1)  # 每个 scene 至少保留 1 秒
                if cut > 0:
                    scene["duration"] = round(dur - cut, 1)
                    overflow -= cut
                if overflow <= 0:
                    break
            logger.warning(f"[剧本生成] 分镜总时长 {total}s 超过目标 {target_duration}s，已截断")

        return raw

    @staticmethod
    def _validate_script_constraints(
        script_content: dict,
        target_duration: int,
    ) -> tuple[list[str], list[str]]:
        """规则层硬约束校验。返回 (auto_fixed, warnings)。"""
        auto_fixed: list[str] = []
        warnings: list[str] = []
        scenes = script_content.get("scenes", [])
        if not scenes:
            return auto_fixed, warnings

        # 1. 总时长校验（_normalize_agent_output 已做截断，这里只记录）
        total = sum(float(s.get("duration", 0)) for s in scenes)
        if total > target_duration:
            auto_fixed.append(f"总时长 {total}s 已截断到 {target_duration}s")

        # 2. 单镜头时长校验
        for scene in scenes:
            dur = float(scene.get("duration", 0))
            if dur > 12:
                scene["duration"] = 12
                auto_fixed.append(f"场景 {scene.get('scene_id')} 时长 {dur}s 已截断到 12s")
            if dur < 1:
                scene["duration"] = 1
                auto_fixed.append(f"场景 {scene.get('scene_id')} 时长 {dur}s 已提升到 1s")

        # 3. 旁白密度预估
        total_chars = sum(len(s.get("text", "")) for s in scenes)
        estimated_tts_seconds = total_chars / 3
        if estimated_tts_seconds > target_duration * 1.5:
            warnings.append(
                f"旁白约 {total_chars} 字（预估 {estimated_tts_seconds:.0f} 秒），"
                f"可能超出 {target_duration} 秒目标时长，生成时会截断"
            )

        # 4. 镜头数量检查
        expected_max = max(3, target_duration // 3)
        if len(scenes) > expected_max:
            warnings.append(
                f"镜头数 {len(scenes)} 偏多（建议不超过 {expected_max} 个），"
                f"可能导致单镜头节奏过快"
            )

        return auto_fixed, warnings

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
            remaining = target_duration - total_sec
            if remaining < 4:
                break
            duration = min(8, remaining)
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


# 模块级单例
script_generation_service = ScriptGenerationService()
