from typing import List, Dict, Any, Optional
import json
import logging
from backend.providers.volcano import VolcanoLLM
from backend.providers.dto.schema import TextUnderstandingRequest

logger = logging.getLogger(__name__)


class LLMService:
    """
    大模型服务类
    封装与大模型的交互，提供因子提取、策略生成等能力
    """

    def __init__(self, llm_client: Optional[VolcanoLLM] = None):
        self.llm_client = llm_client or VolcanoLLM(key=None, model_name=None)

    def extract_common_factors(self, reports: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        从一组爆款视频报告中提取共性因子

        :param reports: 爆款视频结构化报告列表
        :return: 提取到的因子列表，每个因子包含factor_type、name、description、applicable_scenarios、data_schema、example、tags、popularity字段
        """
        # 构造提示词
        prompt = f"""
        你是一个专业的短视频内容分析专家，现在需要从以下{len(reports)}个爆款短视频的结构化解析报告中，提取可复用的共性创作因子。

        因子定义：最细粒度的可复用创作单元，是具体的、可直接落地的创作方法或元素。
        因子类型分为三大类：
        1. content_structure：内容结构类，如HOOK类型、转场类型、节奏模式、时长分布等
        2. product_expression：商品表达类，如卖点展示方式、价格锚点策略、对比方式等
        3. user_operation：用户运营类，如互动引导方式、信任背书类型、紧迫感策略等

        提取要求：
        1. 因子必须是这些报告中共同存在的、反复出现的模式
        2. 每个因子必须包含以下字段：
           - factor_type：因子类型，只能是上述三类之一
           - name：简洁的因子名称，不超过20字
           - description：详细描述因子的含义和使用方法
           - applicable_scenarios：适用场景列表，如["服装", "美妆", "家居"]
           - data_schema：因子的数据结构定义，JSON格式，描述因子包含哪些字段
           - example：具体的示例数据，符合data_schema定义
           - tags：标签列表，便于检索
           - popularity：流行度，0-1之间的浮点数，表示这个因子在报告中出现的频率
        3. 提取的因子数量控制在3-10个之间，优先提取出现频率高、可复用性强的因子
        4. 结果只返回JSON数组，不要有其他解释性文字，确保可以直接解析

        以下是视频报告列表：
        {json.dumps(reports, ensure_ascii=False, indent=2)}
        """

        try:
            # 调用大模型
            request = TextUnderstandingRequest(
                prompt=prompt,
                text="请按照要求提取共性因子，只返回JSON结果",
                max_tokens=2000,
                temperature=0.1
            )

            response = self.llm_client._text_understanding(request)
            content = response.content.strip()

            # 尝试解析JSON
            try:
                # 去掉可能的markdown代码块标记
                if content.startswith("```json"):
                    content = content[7:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()

                factors = json.loads(content)
                logger.info(f"成功提取到{len(factors)}个共性因子")
                return factors

            except json.JSONDecodeError as e:
                logger.error(f"解析大模型返回的因子数据失败: {str(e)}, 原始内容: {content}")
                return []

        except Exception as e:
            logger.error(f"调用大模型提取因子失败: {str(e)}", exc_info=True)
            return []

    def generate_strategy(self, reports: List[Dict[str, Any]], factors: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        基于一组爆款视频报告和提取到的因子，生成抽象创作策略

        :param reports: 爆款视频结构化报告列表
        :param factors: 该簇提取到的共性因子列表
        :return: 生成的策略，包含name、description、applicable_scenarios、core_logic、required_factor_types、optional_factor_types、combination_rules、tags字段
        """
        # 构造提示词
        prompt = f"""
        你是一个专业的短视频策略专家，现在需要基于以下{len(reports)}个爆款短视频的结构化解析报告，以及从中提取到的{len(factors)}个共性创作因子，归纳提炼出一套抽象的创作策略。

        策略定义：抽象的创作方法论，描述一类爆款视频的创作规律和核心逻辑，不绑定具体的因子实例，只定义需要的因子类型和组合规则。

        策略必须包含以下字段：
        1. name：策略名称，简洁明了，不超过20字
        2. description：详细描述策略的核心思想和适用场景
        3. applicable_scenarios：适用场景列表，如["功能性产品", "痛点明确的品类"]
        4. core_logic：核心创作逻辑描述，用箭头表示步骤顺序，如"痛点呈现 → 反转 → 产品展示 → 利益点 → 转化引导"
        5. required_factor_types：必填因子类型列表，说明这个策略必须包含哪些类型的因子
        6. optional_factor_types：可选因子类型列表，说明这个策略可以选择添加哪些类型的因子
        7. combination_rules：因子组合规则描述，说明不同类型因子的使用顺序、时长占比、组合方式等
        8. tags：标签列表，便于检索

        生成要求：
        1. 策略必须是对这组爆款视频共性创作规律的高度抽象总结
        2. 策略只定义因子类型要求，不绑定具体的因子实例
        3. 组合规则要具体、可执行，能够指导后续的视频创作
        4. 结果只返回JSON对象，不要有其他解释性文字，确保可以直接解析

        以下是视频报告列表：
        {json.dumps(reports[:3], ensure_ascii=False, indent=2)}  # 只传前3个报告节省token

        以下是提取到的共性因子列表：
        {json.dumps(factors, ensure_ascii=False, indent=2)}
        """

        try:
            # 调用大模型
            request = TextUnderstandingRequest(
                prompt=prompt,
                text="请按照要求生成创作策略，只返回JSON结果",
                max_tokens=1500,
                temperature=0.3
            )

            response = self.llm_client._text_understanding(request)
            content = response.content.strip()

            # 尝试解析JSON
            try:
                # 去掉可能的markdown代码块标记
                if content.startswith("```json"):
                    content = content[7:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()

                strategy = json.loads(content)
                logger.info(f"成功生成策略: {strategy.get('name', '未命名策略')}")
                return strategy

            except json.JSONDecodeError as e:
                logger.error(f"解析大模型返回的策略数据失败: {str(e)}, 原始内容: {content}")
                return {}

        except Exception as e:
            logger.error(f"调用大模型生成策略失败: {str(e)}", exc_info=True)
            return {}

    def calculate_strategy_success_rate(self, reports: List[Dict[str, Any]], strategy: Dict[str, Any]) -> float:
        """
        计算策略的历史成功率，基于该簇视频的爆款率

        :param reports: 该簇的爆款视频报告列表
        :param strategy: 生成的策略
        :return: 成功率，0-1之间的浮点数
        """
        if not reports:
            return 0.0

        # 简单实现：计算该簇视频的平均爆款分数归一化值
        total_score = 0.0
        valid_count = 0

        for report in reports:
            hot_score = report.get("hot_score", 0)
            if hot_score > 0:
                # 归一化到0-1之间，假设满分100分
                total_score += min(hot_score / 100.0, 1.0)
                valid_count += 1

        if valid_count == 0:
            return 0.0

        average_score = total_score / valid_count
        # 适当调整，避免分数过高或过低
        success_rate = min(max(average_score * 1.1, 0.3), 0.95)
        logger.info(f"计算策略成功率: {success_rate:.2f}，基于{valid_count}个样本")
        return success_rate
