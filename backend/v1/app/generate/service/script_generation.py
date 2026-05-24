"""剧本生成服务"""
import json
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.v1.app.models.project import Project
from backend.v1.app.models.script import Script
from backend.providers import VolcanoLLM, ChatRequest, ChatMessage

logger = logging.getLogger(__name__)


class ScriptGenerationService:
    """剧本生成服务（接入火山引擎 LLM）"""

    def __init__(self):
        """初始化 LLM 客户端"""
        self.llm = VolcanoLLM(key=None, model_name=None)

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
        2. 构造 Prompt + 调用 LLM
        3. 解析生成结果保存到 scripts 表
        4. 更新 project 状态为 script_ready
        """
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            raise ValueError(f"项目不存在: {project_id}")

        # 构造 Prompt
        prompt = self._build_prompt(project, target_duration)

        # 调用 LLM 生成剧本
        try:
            script_content = await self._call_llm(prompt)
            logger.info(f"[剧本生成] LLM 调用成功，project_id={project_id}")
        except Exception as e:
            # LLM 调用失败时使用 Mock 数据作为 fallback
            logger.warning(f"[剧本生成] LLM 调用失败，使用 Mock 数据: {str(e)}")
            script_content = self._mock_generate(project, target_duration)

        script = Script(
            project_id=project_id,
            title=f"{project.title}_带货剧本",
            content=json.dumps(script_content, ensure_ascii=False),
            target_duration=target_duration,
            ai_model="doubao-seed-2.0-pro",
            ai_prompt=prompt,
        )
        db.add(script)

        # 更新项目状态
        project.status = "script_ready"
        await db.commit()
        await db.refresh(script)
        return script

    def _build_prompt(self, project: Project, target_duration: int) -> str:
        """构造 LLM 生成 Prompt"""
        return (
            f"你是一个专业的带货视频编剧。请根据以下商品信息，生成一个{target_duration}秒的带货短视频剧本。\n\n"
            f"## 商品信息\n"
            f"- 商品标题：{project.title}\n"
            f"- 商品描述：{project.description or '无'}\n"
            f"- 商品详情：{project.product_info or '无'}\n\n"
            f"## 输出要求\n"
            f"请严格按照以下 JSON 格式输出，不要输出其他内容：\n"
            f"```json\n"
            f'{{\n'
            f'  "opening": "开场白（吸引注意力的一句话）",\n'
            f'  "body": [\n'
            f'    {{\n'
            f'      "scene": 1,\n'
            f'      "text": "该场景的配音文案",\n'
            f'      "duration_sec": 8,\n'
            f'      "image_keyword": "用于搜索/生成配图的关键词",\n'
            f'      "tts_audio_url": null\n'
            f'    }}\n'
            f'  ],\n'
            f'  "closing": "结束语（引导购买）",\n'
            f'  "full_text": "完整的配音文案（将opening、body中的text、closing拼接）"\n'
            f'}}\n'
            f'```\n\n'
            f"## 注意事项\n"
            f"1. body 中的场景数量根据时长合理分配，每个场景建议 5-10 秒\n"
            f"2. image_keyword 要具体、形象，便于后续配图\n"
            f"3. 文案要口语化、有感染力，适合短视频带货\n"
            f"4. 总时长（所有 scene 的 duration_sec 之和）应接近 {target_duration} 秒"
        )

    async def _call_llm(self, prompt: str) -> dict:
        """调用 LLM 生成剧本"""
        request = ChatRequest(
            messages=[
                ChatMessage(role="system", content="你是一个专业的带货视频编剧，擅长创作短视频剧本。请严格按照要求的 JSON 格式输出。"),
                ChatMessage(role="user", content=prompt),
            ],
            temperature=0.7,
            max_tokens=2048,
        )

        response = self.llm.chat(request)

        # 解析 JSON
        content = response.content
        # 提取 JSON 部分（可能被 ```json ``` 包裹）
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        script_content = json.loads(content.strip())

        # 验证必要字段
        required_fields = ["opening", "body", "closing", "full_text"]
        for field in required_fields:
            if field not in script_content:
                raise ValueError(f"LLM 返回的 JSON 缺少必要字段: {field}")

        return script_content

    def _mock_generate(self, project: Project, target_duration: int) -> dict:
        """Mock 剧本生成（作为 LLM 调用失败的 fallback）"""
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
