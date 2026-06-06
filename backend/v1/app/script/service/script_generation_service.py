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
from backend.v1.app.generate.service.workflow import state as project_workflow_state
from backend.v1.app.generate.service.workflow.limits import normalize_target_duration
from backend.v1.app.script.service.template_script_service import template_script_service
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
                from backend.v1.app.agent import ScriptAgent
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
    ) -> list[Frame]:
        """
        生成带货剧本，逐帧写入 frames 表。
        target_duration 从 projects 表读取。
        :param creation_mode: 创作模式：independent(自主创作，默认)/auto/hot_video/template/strategy
        :param strategy_id: 指定使用的策略ID，仅在strategy模式下有效
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
                base_prompt = self._build_prompt(project, target_duration)
                prompt = template_script_service.build_prompt_with_template(base_prompt, template, template_params)
            else:
                logger.warning(f"模板ID {template_id} 不存在，使用默认生成方式")
                prompt = self._build_prompt(project, target_duration)
        else:
            prompt = self._build_prompt(project, target_duration)

        # 调用 Agent 生成剧本
        try:
            script_content = await self._call_agent(
                prompt,
                project,
                target_duration,
                creation_mode=creation_mode,
                template_id=template_id,
                strategy_id=strategy_id,
                template_params=template_params
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
            template_params=template_params
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

    def _build_prompt(self, project: Project, target_duration: int) -> str:
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
        prompt: str,
        project: Project,
        target_duration: int,
        creation_mode: Optional[str] = None,
        template_id: Optional[str] = None,
        strategy_id: Optional[str] = None,
        template_params: Optional[Dict[str, Any]] = None
    ) -> dict:
        """调用 ScriptAgent 生成剧本"""
        # 提取项目信息
        product_detail = self._format_product_info(project.product_info)

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
            "商品分类": project.category or ""  # 添加分类信息，用于爆款视频查询
        }

        # 过滤空值
        project_info = {k: v for k, v in project_info.items() if v}

        # 获取输出格式要求
        output_format = self._output_format_section(target_duration)

        # 确定创作模式
        # 如果用户指定了template_id但没指定模式，默认使用template模式
        if template_id and not creation_mode:
            creation_mode = "template"
        # 如果没有指定模式，默认使用independent自主创作模式
        elif not creation_mode:
            creation_mode = "independent"

        try:
            # 在独立线程中运行Agent（避免阻塞事件循环）
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
                        template_params=template_params
                    )
                )
            )

            # 验证返回结果
            required_fields = ["video_meta", "scenes", "audio"]
            for field in required_fields:
                if field not in script_content:
                    raise ValueError(f"Agent 返回的 JSON 缺少必要字段: {field}")

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
