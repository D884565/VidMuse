"""剧本生成服务"""
import json
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.v1.app.models.project import Project
from backend.v1.app.models.script import Script


class ScriptGenerationService:
    """剧本生成服务（LLM 部分留接口，当前返回 Mock 数据）"""

    async def generate_script(
        self,
        db: AsyncSession,
        project_id: int,
        target_duration: int = 30,
    ) -> Script:
        """
        生成带货剧本。

        流程：
        1. 从 MySQL 读取 project 的商品信息
        2. 构造 Prompt + 调用 LLM（当前 Mock）
        3. 解析生成结果保存到 scripts 表
        4. 更新 project 状态为 script_ready
        """
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            raise ValueError(f"项目不存在: {project_id}")

        # 构造 Prompt（后续接入真实 LLM 时使用）
        prompt = self._build_prompt(project, target_duration)

        # Mock 剧本内容（后续替换为 LLM 调用）
        script_content = self._mock_generate(project, target_duration)

        script = Script(
            project_id=project_id,
            title=f"{project.title}_带货剧本",
            content=json.dumps(script_content, ensure_ascii=False),
            target_duration=target_duration,
            ai_model="mock",
            ai_prompt=prompt,
        )
        db.add(script)

        # 更新项目状态
        project.status = "script_ready"
        await db.commit()
        await db.refresh(script)
        return script

    def _build_prompt(self, project: Project, target_duration: int) -> str:
        """构造 LLM 生成 Prompt（后续接入真实 LLM 时使用）"""
        return (
            f"你是一个带货视频编剧。根据以下商品信息，生成{target_duration}秒的带货短视频剧本。\n"
            f"商品标题: {project.title}\n"
            f"商品信息: {project.product_info or '无'}\n"
            f"请按 JSON 格式输出：opening / body(scene,text,image_keyword) / closing / full_text"
        )

    def _mock_generate(self, project: Project, target_duration: int) -> dict:
        """Mock 剧本生成（后续替换为真实 LLM 调用）"""
        scenes = []
        total_sec = 0
        scene_count = max(2, target_duration // 8)

        for i in range(scene_count):
            duration = min(8, target_duration - total_sec)
            if duration <= 2:
                break
            scenes.append({
                "scene": i + 1,
                "text": f"{project.title}的第{i+1}个卖点，详细讲解产品优势和使用场景。",
                "duration_sec": duration,
                "image_keyword": f"{project.title}_场景{i+1}",
                "tts_audio_url": None,
            })
            total_sec += duration

        return {
            "opening": f"注意看！这款{project.title}真的太棒了！",
            "body": scenes,
            "closing": "点击下方链接，马上抢购吧！",
            "full_text": f"注意看！这款{project.title}真的太棒了！" +
                        " ".join(s["text"] for s in scenes) +
                        "点击下方链接，马上抢购吧！",
        }


script_generation_service = ScriptGenerationService()
