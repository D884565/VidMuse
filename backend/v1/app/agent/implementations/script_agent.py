"""剧本生成专用Agent
专门用于带货短视频剧本生成，集成灵感模板查询工具，能够自动查询创作因子、策略和成功模板，生成高质量带货剧本。
"""
from typing import Optional, Dict, Any, List
import json
import logging
from .react_agent import ReActAgent
from .prompt_builder import PromptBuilder
from ..tools.text_to_sql_inspiration_tool import TextToSQLInspirationTool
from ..tools.script_creation_tools import HotVideoFusionTool, TemplateGenerationTool, StrategyFactorGenerationTool
from ..tools.similar_video_search_tool import SimilarVideoSearchTool
from ..config import AGENT_CONFIG

logger = logging.getLogger(__name__)


class ScriptPromptBuilder(PromptBuilder):
    """剧本Agent专用Prompt构建器，使用自定义系统提示词"""

    def build_system_prompt(self, agent) -> str:
        """构建剧本Agent专用的系统提示词"""
        tool_names = []
        tool_descriptions = []

        if agent.tool_system:
            tools = agent.tool_system.list_tools()
            tool_names = tools
            for tool_name in tools:
                tool = agent.tool_system.get_tool(tool_name)
                if tool:
                    tool_descriptions.append(f"- {tool.name}: {tool.description}")

        tools_str = "\n".join(tool_descriptions) if tool_descriptions else "无可用工具"

        return f"""你是{agent.name}，{agent.description}。

## 核心能力
你基于ReAct范式工作，可以通过思考-行动-观察的循环来生成高质量的带货短视频剧本。
你有三种创作模式可以选择，也可以调用相关工具获取参考信息，生成更符合爆款规律的剧本。

## 可用工具
{tools_str}

## 创作模式选择指南
你可以根据用户需求和商品特点，选择最合适的创作模式：

### 1. 爆款视频融合模式（工具：hot_video_fusion_creation）
- **适用场景**：用户没有指定模板，希望参考同类爆款视频，追求高转化率
- **使用方式**：传入商品分类信息，查询同类爆款视频作为参考，融合商品信息生成剧本
- **优点**：参考成功案例，转化率有保障，风格符合平台热门趋势

### 2. 模板生成模式（工具：template_creation）
- **适用场景**：用户指定了模板ID，或者需要保持特定风格、结构一致性
- **使用方式**：传入模板ID和参数，严格按照模板结构和逻辑生成剧本
- **优点**：风格统一，符合特定模板的成功规律，质量稳定

### 3. 策略因子模式（工具：strategy_factor_creation）
- **适用场景**：需要灵活创新，或者用户有特定的策略要求
- **使用方式**：自动推荐最适合的创作策略和因子，按照策略规则组合生成剧本
- **优点**：灵活性高，创新性强，适合追求差异化的场景

### 4. 相似爆款参考模式（工具：search_similar_hot_videos）
- **适用场景**：已有视频解析报告，希望借鉴同类型爆款视频的成功经验
- **使用方式**：传入视频解析报告内容，检索相似爆款视频的分析报告作为参考
- **优点**：基于真实爆款案例分析，成功率更高，创意更贴合用户需求

### 5. 自主创作模式（默认推荐）
- **适用场景**：所有场景，尤其适合需要快速生成、没有指定模板或参考要求的情况
- **使用方式**：不需要调用任何工具，完全基于你的专业编剧经验，结合商品信息自主创作高质量剧本
- **创作框架（内置专业方法论）**：
  1. **黄金3秒法则**：开场用痛点、疑问、惊喜等方式瞬间抓住观众注意力
  2. **AIDA模型**：Attention(吸引注意) → Interest(激发兴趣) → Desire(唤起欲望) → Action(引导行动)
  3. **卖点结构化**：每个场景突出1个核心卖点，逻辑清晰，层层递进
  4. **情绪引导**：从痛点到解决方案再到美好体验，引导用户情绪变化
  5. **转化率优化**：合理安排价格展示、优惠信息、行动号召的位置
- **优点**：生成速度快，灵活性高，针对性强，完全适配当前商品特点

## 工作流程
1. 理解用户需求：仔细分析用户提供的商品信息、目标受众、风格要求、指定的创作模式、是否有参考视频报告等
2. 选择创作模式：
   - 如果用户明确指定了模式，使用用户指定的模式
   - **默认优先使用自主创作模式**，不需要调用任何工具
   - 只有当用户明确要求使用参考、模板或策略时，才考虑使用工具模式
3. 工具调用（仅工具模式需要）：
   - 根据选择的模式调用对应的工具获取参考信息
   - 工具结果仅作为参考，不要被限制创作思路
4. 构思剧本：
   - 自主创作模式：直接使用内置的专业创作框架，结合商品信息构思
   - 工具模式：融合参考信息和商品特点，进行创新性创作
5. 输出结果：严格按照要求的JSON格式输出剧本，不要包含任何额外解释文字

## 模式选择指南
- 优先使用用户明确指定的创作模式，不要自行切换
- 如果用户没有指定模式，**默认优先使用自主创作模式**，凭借你的专业经验直接生成剧本
- 只有当用户明确要求参考爆款、使用模板或策略时，再调用对应的工具
- 如果用户提供了视频解析报告，且明确要求参考相似视频，再调用search_similar_hot_videos工具
- 工具返回的创作指南和相似视频分析仅作为参考，最终创作要结合当前商品的独特性进行创新
- 如果工具调用失败，直接使用自主创作模式，不要因为工具问题影响生成速度和质量

## 响应规则
### 全新剧本生成
1. 最终输出必须是严格的JSON格式，不要包含任何其他解释性文字
2. 剧本结构标准（自主创作默认遵循）：
   - 3-5个场景，总时长12-20秒，符合短视频完播率规律
   - 场景1（3-5秒）：Hook开场，用痛点、反问、惊喜等方式瞬间抓眼球
   - 场景2（4-6秒）：核心卖点展示，讲清楚产品能解决什么问题
   - 场景3（3-5秒）：产品优势/细节展示，建立信任
   - 场景4（2-4秒）：价格/优惠/行动号召，引导转化
3. 文案要求：
   - 口语化、有感染力，像真人带货一样自然
   - 避免书面语和专业术语，用用户听得懂的话
   - 有节奏感，重点内容可以适当重复强调
4. 画面描述要求：
   - image_prompt要详细：包含主体、动作、背景、光线、色调、构图，适合AI生成
   - video_prompt要具体：描述镜头运动、画面变化、动态效果
   - overlay.text要简短有力，不超过10个字，突出核心信息
5. 如果无法生成符合要求的剧本，坦诚告知问题，不要编造信息

### 剧本修改任务
当用户要求修改已有剧本时，遵循以下规则：
1. 仔细理解用户的修改指令，只修改用户要求的部分，其他内容保持完全不变
2. 保持剧本的整体结构、场景顺序、未修改部分的内容完全一致
3. 如果修改涉及时长调整，自动调整相关场景的时长，确保总时长符合要求
4. 修改完成后，输出完整的JSON格式剧本，不要只输出修改部分
5. 在JSON的最外层添加"modification_note"字段，详细说明：
   - 修改了哪些内容（具体到场景编号或字段）
   - 为什么这么修改（对应用户的哪些要求）
   - 其他注意事项或建议
6. 确保修改后的剧本仍然符合所有格式要求和字段完整性
"""

class ScriptAgent(ReActAgent):
    """
    剧本生成专用Agent
    基于ReAct范式，集成TextToSQL灵感查询工具，专门用于带货短视频剧本生成
    """

    def __init__(
        self,
        agent_id: str = "script_agent",
        name: str = "专业带货视频编剧",
        description: str = "专业的带货视频编剧，擅长创作高转化率的短视频带货剧本，可以查询历史成功模板和创作策略。",
        config: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None,
        max_iterations: Optional[int] = None
    ):
        """
        初始化剧本生成Agent
        :param agent_id: Agent唯一标识
        :param name: Agent名称
        :param description: Agent描述
        :param config: 自定义配置
        :param model: 使用的模型
        :param max_iterations: 最大迭代次数，默认4次
        """
        super().__init__(
            agent_id=agent_id,
            name=name,
            description=description,
            config=config,
            model=model,
            max_iterations=max_iterations or 4  # 剧本生成不需要太多迭代
        )

        # 使用自定义的Prompt构建器
        self.context_builder = ScriptPromptBuilder()

        # 注册基础查询工具
        self.tool_system.register_tool(TextToSQLInspirationTool())

        # 注册剧本创作专用工具
        self.tool_system.register_tool(HotVideoFusionTool())
        self.tool_system.register_tool(TemplateGenerationTool())
        self.tool_system.register_tool(StrategyFactorGenerationTool())
        # 注册相似爆款视频检索工具
        self.tool_system.register_tool(SimilarVideoSearchTool())

    async def generate_script(
        self,
        project_info: Dict[str, Any],
        target_duration: int,
        output_format: str = "",
        creation_mode: Optional[str] = None,
        template_id: Optional[str] = None,
        strategy_id: Optional[str] = None,
        template_params: Optional[Dict[str, Any]] = None,
        video_report: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        生成剧本的专用方法
        :param project_info: 项目信息，包含标题、描述、用户prompt、商品信息等
        :param target_duration: 目标视频时长（秒）
        :param output_format: 输出格式要求
        :param creation_mode: 创作模式：independent(自主创作)/auto/hot_video/template/strategy，可选，默认independent
        :param template_id: 模板ID，当creation_mode为template时必填
        :param strategy_id: 策略ID，当creation_mode为strategy时可选
        :param template_params: 模板参数，当使用模板时可选
        :param video_report: 参考视频解析报告内容，用于检索相似爆款视频
        :param context: 额外上下文信息
        :return: 生成的剧本数据（字典格式）
        """
        # 构建用户查询prompt
        prompt_parts = [
            f"请根据以下信息生成一个约{target_duration}秒的带货短视频剧本。\n",
            "## 项目信息\n"
        ]

        # 添加项目信息
        for key, value in project_info.items():
            if value:  # 只添加非空字段
                prompt_parts.append(f"- {key}: {value}")

        # 添加创作模式说明
        if creation_mode:
            mode_desc = {
                "independent": "使用自主创作模式，完全基于专业编剧经验生成，不需要参考外部数据",
                "auto": "自动选择最合适的创作模式",
                "hot_video": "使用爆款视频融合模式，参考同类爆款视频生成",
                "template": f"使用模板生成模式，模板ID：{template_id}",
                "strategy": "使用策略因子模式生成",
                "similar_video": "使用相似爆款视频参考模式，基于提供的视频报告检索相似案例"
            }.get(creation_mode, "自主创作模式")

            prompt_parts.append(f"\n## 创作模式要求\n- 指定模式：{mode_desc}")

            if creation_mode == "template" and template_id:
                prompt_parts.append(f"- 模板ID：{template_id}")
                if template_params:
                    prompt_parts.append(f"- 模板参数：{json.dumps(template_params, ensure_ascii=False)}")

            if creation_mode == "strategy" and strategy_id:
                prompt_parts.append(f"- 策略ID：{strategy_id}")

        # 添加参考视频报告
        if video_report:
            prompt_parts.append(f"\n## 参考视频解析报告\n{video_report}")
            prompt_parts.append("\n提示：你可以调用search_similar_hot_videos工具，基于以上报告检索相似的爆款视频作为创作参考。")

        # 添加输出格式要求
        if output_format:
            prompt_parts.append(f"\n{output_format}")

        user_prompt = "\n".join(prompt_parts)

        # 构建运行上下文
        run_context = context or {}
        run_context["target_duration"] = target_duration
        run_context["project_info"] = project_info
        if video_report:
            run_context["video_report"] = video_report

        # 调用Agent运行
        result = self.run(user_prompt, run_context)

        if not result.get("success"):
            raise RuntimeError(f"Agent执行失败: {result.get('error', '未知错误')}")

        # 解析返回的JSON
        content = result.get("answer", "")
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        try:
            script_content = json.loads(content.strip())
            return script_content
        except json.JSONDecodeError as e:
            logger.error(f"解析Agent返回的JSON失败: {str(e)}, 内容: {content[:200]}...")
            raise RuntimeError(f"剧本生成失败，返回格式错误: {str(e)}")

    async def revise_script(
        self,
        current_script: Dict[str, Any],
        revision_instruction: str,
        modification_history: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        修改已有剧本的专用方法
        :param current_script: 当前完整的剧本JSON数据
        :param revision_instruction: 用户的修改指令，自然语言描述
        :param modification_history: 历史修改记录，可选，用于多轮修改上下文
        :param context: 额外上下文信息
        :return: 修改后的剧本数据，包含modification_note字段说明修改内容
        """
        # 构建修改任务的prompt
        prompt_parts = [
            "## 剧本修改任务",
            "请根据以下修改指令修改现有剧本，只修改要求的部分，其他内容保持不变。\n",
            "### 当前剧本内容：",
            json.dumps(current_script, ensure_ascii=False, indent=2),
            "\n### 修改指令：",
            revision_instruction
        ]

        # 添加修改历史（如果有）
        if modification_history:
            prompt_parts.append("\n### 历史修改记录：")
            for i, record in enumerate(modification_history, 1):
                prompt_parts.append(
                    f"{i}. 指令：{record.get('instruction', '')}\n   修改说明：{record.get('note', '')}"
                )

        # 添加输出要求
        prompt_parts.append("""
### 输出要求：
1. 输出完整的修改后的JSON格式剧本
2. 保持原有所有字段不变，只修改需要更新的内容
3. 在JSON最外层添加modification_note字段，详细说明：
   - 修改了哪些内容（具体到场景编号、字段名称）
   - 修改的原因和依据
   - 其他注意事项或建议
4. 不要输出任何JSON以外的解释性文字
        """)

        user_prompt = "\n".join(prompt_parts)

        # 构建运行上下文
        run_context = context or {}
        run_context["task_type"] = "revision"
        run_context["modification_history"] = modification_history or []

        # 调用Agent运行，禁用工具调用（修改阶段不需要调用创作工具，直接基于现有剧本修改）
        # 临时禁用工具，避免不必要的查询
        original_tools = self.tool_system
        try:
            # 先清空工具，修改剧本不需要调用外部工具
            self.tool_system = type(original_tools)()

            result = self.run(user_prompt, run_context)

            if not result.get("success"):
                raise RuntimeError(f"Agent执行修改失败: {result.get('error', '未知错误')}")

            # 解析返回的JSON
            content = result.get("answer", "")
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            try:
                revised_script = json.loads(content.strip())

                # 验证返回结果包含必要字段
                if "video_meta" not in revised_script or "scenes" not in revised_script:
                    raise ValueError("修改后的剧本缺少必要字段")

                # 如果没有modification_note，自动生成一个
                if "modification_note" not in revised_script:
                    revised_script["modification_note"] = "已根据指令完成剧本修改"

                return revised_script

            except json.JSONDecodeError as e:
                logger.error(f"解析修改后的JSON失败: {str(e)}, 内容: {content[:200]}...")
                raise RuntimeError(f"剧本修改失败，返回格式错误: {str(e)}")

        finally:
            # 恢复原来的工具系统
            self.tool_system = original_tools


# 模块级单例
try:
    script_agent = ScriptAgent()
except Exception as e:
    logger.warning(f"初始化全局ScriptAgent失败: {str(e)}")
    script_agent = None
