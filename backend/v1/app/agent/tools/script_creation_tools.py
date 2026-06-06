"""剧本创作专用工具集
提供三种剧本创作方式的工具封装：
1. 爆款视频融合模式：自动匹配同类爆款视频，融合商品信息生成剧本
2. 指定模板模式：根据用户指定的灵感模板生成剧本
3. 策略因子模式：基于策略+因子+约束生成剧本
"""
from typing import Dict, Any, List, Optional
import json
import logging
import asyncio
from ..core.tool import BaseTool
from ..utils.tool_registry import register_tool
from .video_library_tool import VideoLibraryQueryTool
from .text_to_sql_inspiration_tool import TextToSQLInspirationTool
# 导入移到execute方法内部，避免循环导入
# from backend.v1.app.script.service.template_script_service import template_script_service
from backend.store.database.async_database import get_db

logger = logging.getLogger(__name__)


@register_tool
class HotVideoFusionTool(BaseTool):
    """
    爆款视频融合创作工具
    自动查询同类商品的爆款视频脚本，融合当前商品信息生成高质量剧本
    """
    name: str = "hot_video_fusion_creation"
    description: str = "爆款视频融合创作工具，查询同类商品的爆款视频脚本作为参考，融合当前商品信息生成剧本。适用于需要参考成功案例、追求高转化率的场景。"
    parameters_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "description": "商品分类名称，例如：'手机', '电脑', '服装'等，用于查询同类爆款视频"
            },
            "category_id": {
                "type": "integer",
                "description": "商品分类ID，优先级高于category名称"
            },
            "product_info": {
                "type": "object",
                "description": "当前商品的详细信息，包含标题、描述、卖点、价格等"
            },
            "target_duration": {
                "type": "integer",
                "description": "目标视频时长（秒），默认15秒",
                "default": 15
            },
            "limit": {
                "type": "integer",
                "description": "参考爆款视频数量，默认返回3个最热门的",
                "default": 3
            },
            "min_hot_score": {
                "type": "integer",
                "description": "最低热度分数，默认80",
                "default": 80
            }
        },
        "required": ["product_info"]
    }

    def __init__(self):
        super().__init__()
        self.video_tool = VideoLibraryQueryTool()

    def execute(self, parameters: Dict[str, Any]) -> str:
        """
        执行爆款视频融合创作
        :param parameters: 工具参数
        :return: JSON格式的创作参考结果
        """
        try:
            product_info = parameters.get("product_info", {})
            category = parameters.get("category")
            category_id = parameters.get("category_id")
            target_duration = parameters.get("target_duration", 15)
            limit = parameters.get("limit", 3)
            min_hot_score = parameters.get("min_hot_score", 80)

            # 如果没有提供分类，尝试从商品信息中提取
            if not category and not category_id:
                category = product_info.get("category") or product_info.get("type") or ""
                if not category:
                    return json.dumps({
                        "success": False,
                        "error": "缺少商品分类信息，无法查询同类爆款视频"
                    }, ensure_ascii=False)

            # 调用视频库查询工具
            video_params = {
                "category": category,
                "category_id": category_id,
                "limit": limit,
                "min_hot_score": min_hot_score
            }

            video_result_str = self.video_tool.execute(video_params)
            video_result = json.loads(video_result_str)

            if not video_result.get("success"):
                return json.dumps({
                    "success": False,
                    "error": f"查询爆款视频失败: {video_result.get('error', '未知错误')}"
                }, ensure_ascii=False)

            videos = video_result.get("data", {}).get("videos", [])
            if not videos:
                return json.dumps({
                    "success": False,
                    "error": "未找到同类爆款视频参考"
                }, ensure_ascii=False)

            # 格式化参考信息
            reference_videos = []
            for video in videos:
                reference_videos.append({
                    "video_id": video.get("video_id"),
                    "title": video.get("title"),
                    "description": video.get("description"),
                    "hot_score": video.get("hot_score"),
                    "tags": video.get("tags", []),
                    "url": video.get("url")
                })

            # 构建融合提示
            fusion_guide = f"""
## 爆款视频参考信息
已找到{len(reference_videos)}个同类爆款视频作为参考，请结合这些视频的优点和当前商品信息生成剧本。

### 参考视频列表：
{json.dumps(reference_videos, ensure_ascii=False, indent=2)}

### 当前商品信息：
{json.dumps(product_info, ensure_ascii=False, indent=2)}

### 创作要求：
1. 参考爆款视频的结构、话术、节奏，但不要完全照搬
2. 突出当前商品的独特卖点和优势
3. 总时长控制在{target_duration}秒左右
4. 保持短视频带货的快节奏和感染力
            """

            return json.dumps({
                "success": True,
                "mode": "hot_video_fusion",
                "reference_videos": reference_videos,
                "fusion_guide": fusion_guide,
                "message": f"成功获取{len(reference_videos)}个爆款视频参考"
            }, ensure_ascii=False, default=str)

        except Exception as e:
            logger.error(f"爆款视频融合创作失败: {str(e)}", exc_info=True)
            return json.dumps({
                "success": False,
                "error": str(e)
            }, ensure_ascii=False)


@register_tool
class TemplateGenerationTool(BaseTool):
    """
    模板生成创作工具
    根据用户指定的灵感模板ID，加载模板、策略和关联因子，按照模板规范生成剧本
    """
    name: str = "template_creation"
    description: str = "模板生成创作工具，根据指定的灵感模板ID生成剧本。适用于有明确模板要求、需要保持风格一致性的场景。"
    parameters_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "template_id": {
                "type": "string",
                "description": "灵感模板ID，必填参数"
            },
            "template_params": {
                "type": "object",
                "description": "模板自定义参数，用于填充模板中的变量"
            },
            "product_info": {
                "type": "object",
                "description": "当前商品的详细信息，包含标题、描述、卖点、价格等"
            },
            "target_duration": {
                "type": "integer",
                "description": "目标视频时长（秒），默认15秒",
                "default": 15
            }
        },
        "required": ["template_id", "product_info"]
    }

    def execute(self, parameters: Dict[str, Any]) -> str:
        """
        执行模板生成创作
        :param parameters: 工具参数
        :return: JSON格式的创作参考结果
        """
        try:
            template_id = parameters.get("template_id")
            template_params = parameters.get("template_params", {})
            product_info = parameters.get("product_info", {})
            target_duration = parameters.get("target_duration", 15)

            if not template_id:
                return json.dumps({
                    "success": False,
                    "error": "缺少模板ID参数"
                }, ensure_ascii=False)

            # 异步加载模板数据
            async def load_template_data():
                # 动态导入避免循环依赖
                from backend.v1.app.script.service.template_script_service import template_script_service
                async for db in get_db():
                    return await template_script_service.process_template_data(
                        db, template_id, template_params
                    )

            template_data = asyncio.run(load_template_data())
            template = template_data.get("template")

            if not template:
                return json.dumps({
                    "success": False,
                    "error": f"模板ID {template_id} 不存在"
                }, ensure_ascii=False)

            strategy = template_data.get("strategy")
            used_factors = template_data.get("used_factors", [])

            # 构建模板创作指南
            template_guide_parts = [
                f"## 模板创作指南",
                f"### 模板基本信息",
                f"- 模板名称：{template.get('name', '')}",
                f"- 模板描述：{template.get('description', '')}",
                f"- 模板成功率：{template.get('success_rate', 0)}",
                f"- 模板使用次数：{template.get('usage_count', 0)}"
            ]

            if strategy:
                template_guide_parts.extend([
                    f"\n### 关联创作策略",
                    f"- 策略名称：{strategy.get('name', '')}",
                    f"- 策略描述：{strategy.get('description', '')}",
                    f"- 核心逻辑：{strategy.get('core_logic', '')}",
                    f"- 组合规则：{strategy.get('combination_rules', '')}"
                ])

            if used_factors:
                template_guide_parts.append("\n### 关联创作因子")
                for factor in used_factors:
                    usage_type = "必填" if factor.get("factor_usage_type") == 1 else "可选"
                    template_guide_parts.append(
                        f"- [{usage_type}] {factor.get('name', '')}: {factor.get('description', '')}"
                    )

            if template_params:
                template_guide_parts.extend([
                    f"\n### 用户自定义参数",
                    json.dumps(template_params, ensure_ascii=False, indent=2)
                ])

            template_guide_parts.extend([
                f"\n### 当前商品信息",
                json.dumps(product_info, ensure_ascii=False, indent=2),
                f"\n### 创作要求",
                f"1. 严格遵循模板的结构和创作逻辑",
                f"2. 必须包含所有必填因子的内容",
                f"3. 结合商品特性进行内容创作，不要照搬模板示例",
                f"4. 总时长控制在{target_duration}秒左右"
            ])

            template_guide = "\n".join(template_guide_parts)

            return json.dumps({
                "success": True,
                "mode": "template_creation",
                "template": template,
                "strategy": strategy,
                "used_factors": used_factors,
                "template_params": template_params,
                "template_guide": template_guide,
                "message": f"成功加载模板「{template.get('name')}」"
            }, ensure_ascii=False, default=str)

        except Exception as e:
            logger.error(f"模板生成创作失败: {str(e)}", exc_info=True)
            return json.dumps({
                "success": False,
                "error": str(e)
            }, ensure_ascii=False)


@register_tool
class StrategyFactorGenerationTool(BaseTool):
    """
    策略因子生成创作工具
    根据商品类型和用户需求，查询最合适的创作策略和因子，按照策略规则组合生成剧本
    """
    name: str = "strategy_factor_creation"
    description: str = "策略因子生成创作工具，自动查询最适合的创作策略和因子，按照策略规则组合生成剧本。适用于需要灵活创作、追求创新的场景。"
    parameters_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "product_info": {
                "type": "object",
                "description": "当前商品的详细信息，包含标题、描述、卖点、价格、分类等"
            },
            "strategy_id": {
                "type": "string",
                "description": "可选参数，指定使用的策略ID，不指定则自动推荐最合适的策略"
            },
            "target_duration": {
                "type": "integer",
                "description": "目标视频时长（秒），默认15秒",
                "default": 15
            },
            "constraints": {
                "type": "object",
                "description": "创作约束条件，如风格要求、禁用内容、重点强调等"
            }
        },
        "required": ["product_info"]
    }

    def __init__(self):
        super().__init__()
        self.sql_tool = TextToSQLInspirationTool()

    def execute(self, parameters: Dict[str, Any]) -> str:
        """
        执行策略因子生成创作
        :param parameters: 工具参数
        :return: JSON格式的创作参考结果
        """
        try:
            product_info = parameters.get("product_info", {})
            strategy_id = parameters.get("strategy_id")
            target_duration = parameters.get("target_duration", 15)
            constraints = parameters.get("constraints", {})

            # 获取商品分类
            category = product_info.get("category") or product_info.get("type") or "通用"

            # 查询策略
            if strategy_id:
                # 指定策略ID，查询详情
                strategy_query = f"查询strategy_id为'{strategy_id}'的创作策略详细信息"
            else:
                # 自动推荐策略，查询高成功率的策略
                strategy_query = f"查询适用于{category}类商品、成功率最高的前3个创作策略"

            strategy_result_str = self.sql_tool.execute({"query": strategy_query, "limit": 3})
            strategy_result = json.loads(strategy_result_str)

            if not strategy_result.get("success") or not strategy_result.get("data"):
                return json.dumps({
                    "success": False,
                    "error": f"查询创作策略失败: {strategy_result.get('error', '未找到合适的创作策略')}"
                }, ensure_ascii=False)

            strategies = strategy_result.get("data", [])
            selected_strategy = strategies[0] if strategies else None

            if not selected_strategy:
                return json.dumps({
                    "success": False,
                    "error": "未找到合适的创作策略"
                }, ensure_ascii=False)

            # 查询该策略适用的因子
            factor_query = f"查询流行度大于0.7、适用于{category}类商品的创作因子，按流行度排序"
            factor_result_str = self.sql_tool.execute({"query": factor_query, "limit": 10})
            factor_result = json.loads(factor_result_str)
            factors = factor_result.get("data", []) if factor_result.get("success") else []

            # 构建策略因子创作指南
            strategy_guide_parts = [
                f"## 策略因子创作指南",
                f"### 推荐创作策略",
                f"- 策略名称：{selected_strategy.get('name', '')}",
                f"- 策略描述：{selected_strategy.get('description', '')}",
                f"- 核心逻辑：{selected_strategy.get('core_logic', '')}",
                f"- 组合规则：{selected_strategy.get('combination_rules', '')}",
                f"- 成功率：{selected_strategy.get('success_rate', 0)}"
            ]

            if factors:
                strategy_guide_parts.append("\n### 推荐创作因子（按流行度排序）")
                for i, factor in enumerate(factors[:5], 1):
                    strategy_guide_parts.append(
                        f"{i}. {factor.get('name', '')}: {factor.get('description', '')} (流行度: {factor.get('popularity', 0)})"
                    )

            if constraints:
                strategy_guide_parts.extend([
                    f"\n### 创作约束条件",
                    json.dumps(constraints, ensure_ascii=False, indent=2)
                ])

            strategy_guide_parts.extend([
                f"\n### 当前商品信息",
                json.dumps(product_info, ensure_ascii=False, indent=2),
                f"\n### 创作要求",
                f"1. 严格遵循所选策略的核心逻辑和组合规则",
                f"2. 灵活运用推荐的创作因子，突出商品卖点",
                f"3. 满足所有约束条件",
                f"4. 总时长控制在{target_duration}秒左右"
            ])

            strategy_guide = "\n".join(strategy_guide_parts)

            return json.dumps({
                "success": True,
                "mode": "strategy_factor_creation",
                "selected_strategy": selected_strategy,
                "recommended_factors": factors[:5],  # 返回前5个最相关的因子
                "other_strategies": strategies[1:3],  # 返回其他可选策略
                "strategy_guide": strategy_guide,
                "message": f"成功推荐策略「{selected_strategy.get('name')}」和{len(factors)}个相关因子"
            }, ensure_ascii=False, default=str)

        except Exception as e:
            logger.error(f"策略因子生成创作失败: {str(e)}", exc_info=True)
            return json.dumps({
                "success": False,
                "error": str(e)
            }, ensure_ascii=False)
