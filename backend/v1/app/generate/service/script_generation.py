"""剧本生成服务"""
import json
import asyncio
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.v1.app.models.project import Project
from backend.v1.app.models.frame import Frame
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


class ScriptGenerationService:
    """剧本生成服务（接入火山引擎 LLM）"""

    def __init__(self):
        """初始化 LLM 客户端"""
        self.llm = VolcanoLLM(key=None, model_name=None)

    async def generate_script(
        self,
        db: AsyncSession,
        project_id: int,
        target_duration: int = 15,
    ) -> list[Frame]:
        """
        生成带货剧本，逐帧写入 frames 表。

        :returns: Frame 列表
        """
        # 限制总时长在 12-20 秒
        target_duration = max(12, min(20, target_duration))

        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            raise ValueError(f"项目不存在: {project_id}")

        # 检索相关参考资料
        reference = self._mock_retrieve(project)

        # 构造 Prompt
        prompt = self._build_prompt(project, target_duration, reference)

        # 调用 LLM 生成剧本
        try:
            script_content = await self._call_llm(prompt)
            logger.info(f"[剧本生成] LLM 调用成功，project_id={project_id}")
        except Exception as e:
            logger.warning(f"[剧本生成] LLM 调用失败，使用 Mock 数据: {str(e)}")
            script_content = self._mock_generate(project, target_duration)

        # 逐场景写入 frames 表
        scenes = script_content.get("scenes", [])
        frames = []
        for scene in scenes:
            visual = scene.get("visual", {})
            overlay = visual.get("overlay", {})

            frame = Frame(
                project_id=project_id,
                sequence=scene.get("scene_id", 0),
                scene_type=SCENE_TYPE_MAP.get(scene.get("type", ""), 0),
                description=visual.get("image_prompt", scene.get("text", "")),
                prompt=visual.get("video_prompt", ""),
                text_overlay=overlay.get("text", ""),
                duration=scene.get("duration", 3),
                transition_type=0,
                status=0,  # 待生成
                ai_params={
                    "camera": visual.get("camera", ""),
                    "mood": visual.get("mood", ""),
                    "overlay_position": overlay.get("position", "bottom"),
                    "overlay_style": overlay.get("style", "highlight"),
                    "voice_style": scene.get("voice_style", ""),
                    "text": scene.get("text", ""),
                },
                metadata_={
                    "scene_type_str": scene.get("type", ""),
                    "hook_line": script_content.get("video_meta", {}).get("hook_line", ""),
                },
            )
            db.add(frame)
            frames.append(frame)

        # 更新项目状态
        project.status = "script_ready"
        await db.commit()

        # 刷新所有 frame 获取生成的 id
        for frame in frames:
            await db.refresh(frame)

        logger.info(f"[剧本生成] 已写入 {len(frames)} 个帧，project_id={project_id}")
        return frames

    def _mock_retrieve(self, project: Project) -> str:
        """
        检索相关参考资料（Mock）。

        TODO: 接入知识库检索（ChromaDB），根据商品信息检索：
        - 同类商品的热门带货文案
        - 带货视频脚本模板
        - 行业话术和转化技巧
        """
        return (
            f"## 参考资料（同品类热门带货文案）\n\n"
            f"### 热门文案模板\n"
            f"1. 开场hook：「还在为选XX发愁？这款XX让你一步到位！」\n"
            f"2. 卖点展示：「采用XX工艺，XX材质，用过的都说好」\n"
            f"3. 价格锚定：「原价XX，今天直播间专属价只要XX」\n"
            f"4. 紧迫感：「库存只剩最后XX件，拍完就恢复原价」\n"
            f"5. 行动号召：「点击下方小黄车，立即下单！」\n\n"
            f"### 带货视频拍摄要点\n"
            f"- 前3秒必须抓住注意力（提出痛点或制造悬念）\n"
            f"- 每个镜头不超过5秒，保持节奏紧凑\n"
            f"- 产品特写镜头要展示细节质感\n"
            f"- 结尾要有明确的行动指引\n\n"
            f"### {project.title} 相关卖点参考\n"
            f"- 品质保证，正品行货\n"
            f"- 性价比高，同价位最优\n"
            f"- 用户好评率98%\n"
            f"- 支持7天无理由退换"
        )

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
        """构造 LLM 生成 Prompt"""
        # 解析 product_info JSON，格式化为可读文本
        product_detail = self._format_product_info(project.product_info)

        return (
            f"你是一个专业的带货视频编剧，擅长创作短视频带货剧本。请根据以下商品信息和参考资料，生成一个约{target_duration}秒的带货短视频剧本。\n\n"
            f"## 商品信息\n"
            f"- 商品标题：{project.title}\n"
            f"- 商品描述：{project.description or '无'}\n"
            f"{product_detail}\n\n"
            f"{reference}\n\n"
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
            f'        "image_prompt": "图片生成提示词：详细描述画面内容，包括主体、背景、光线、色调、构图。例如：一位年轻女性手持木吉他坐在窗边，温暖的阳光洒在吉他面板上，背景是简约的白色墙壁，暖色调，竖屏构图",\n'
            f'        "video_prompt": "视频生成提示词：描述镜头运动和动态效果。例如：镜头从吉他全景缓慢推近至面板特写，阳光光斑微微晃动，手指轻拨琴弦",\n'
            f'        "camera": "镜头运动方式（push_in/pull_out/pan_left/pan_right/static/close_up/wide_shot）",\n'
            f'        "mood": "画面氛围（warm/bright/dark/energetic/elegant）",\n'
            f'        "overlay": {{\n'
            f'          "text": "画面上叠加的关键文字（如价格、卖点、行动号召），不超过10个字，不需要叠加文字时留空字符串",\n'
            f'          "position": "文字位置（top/center/bottom，默认bottom）",\n'
            f'          "style": "文字风格（highlight/price_tag/call_to_action/subtle，默认highlight）"\n'
            f'        }}\n'
            f'      }}\n'
            f'    }}\n'
            f'  ],\n'
            f'  "audio": {{\n'
            f'    "tts_voice": "zh_female_cancan_mars_bigtts",\n'
            f'    "bgm": "背景音乐风格描述或文件名",\n'
            f'    "bgm_volume": 0.3\n'
            f'  }}\n'
            f'}}\n'
            f'```\n\n'
            f"## 场景类型说明\n"
            f"- hook: 开场，前3秒抓住注意力，提出痛点或制造悬念（3-5秒）\n"
            f"- selling_point: 卖点展示，展示产品核心优势（4-8秒）\n"
            f"- detail: 细节特写，展示产品质感和工艺（3-6秒）\n"
            f"- social_proof: 口碑背书，用户好评或权威认证（3-5秒）\n"
            f"- price: 价格优惠，制造紧迫感（3-5秒）\n"
            f"- cta: 行动号召，引导购买（3-5秒）\n\n"
            f"## 注意事项\n"
            f"1. 总时长必须在 12-20 秒之间（当前目标 {target_duration} 秒），scenes 数量 3-5 个，每个场景 duration 在 3-8 秒\n"
            f"2. image_prompt 要足够详细，能独立生成高质量配图（包含主体、背景、光线、色调、构图）\n"
            f"3. video_prompt 要描述具体的镜头运动和画面变化，让视频模型知道该怎么动\n"
            f"4. 文案要口语化、有感染力，适合短视频带货，不要书面语\n"
            f"5. voice_style 可选：excited/confident/urgent/warm/professional\n"
            f"6. 前3秒是黄金时间，hook 必须足够吸引人\n"
            f"7. camera 要和画面内容匹配，特写用 close_up，全景用 wide_shot\n"
            f"8. overlay 用于在画面上叠加关键文字，提高转化率。以下场景建议添加 overlay：\n"
            f"   - hook 场景：叠加商品名称或核心卖点（如「新手首选」）\n"
            f"   - selling_point/detail 场景：叠加关键参数或卖点关键词（如「云杉木面板」「好评率98%」）\n"
            f"   - price 场景：叠加价格信息（如「原价699 现价649」「限时特惠」）\n"
            f"   - cta 场景：叠加行动号召（如「点击下单」「立即抢购」）\n"
            f"   - 不需要叠加文字的场景（如纯画面展示），overlay.text 留空字符串\n"
            f"   - overlay.text 必须简短有力，不超过10个字"
        )

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
