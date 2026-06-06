from typing import List, Dict, Any, Optional
import json
import logging
from backend.providers.volcano import VolcanoLLM
from backend.providers.dto.schema import TextUnderstandingRequest
from backend.v1.app.pipeline.utils.prompt_manager import prompt_manager
from backend.v1.app.pipeline.utils.template_validator import validate_with_schema

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
        从一组爆款视频报告中提取共性因子，分为两步：
        1. 第一次调用大模型提取视频共性特征
        2. 第二次调用大模型基于特征提取可复用因子

        :param reports: 爆款视频结构化报告列表
        :return: 提取到的因子列表，每个因子包含factor_type、name、description、applicable_scenarios、data_schema、example、tags、popularity字段
        """
        try:
            # 第一步：提取视频共性特征
            logger.info("第一步：调用大模型提取视频共性特征")
            features_prompt = prompt_manager.get_common_features_extraction_prompt(
                report_count=len(reports),
                reports=json.dumps(reports, ensure_ascii=False, indent=2)
            )

            features_request = TextUnderstandingRequest(
                prompt=features_prompt,
                text="请按照要求提取视频共性特征，只返回JSON结果",
                max_tokens=1500,
                temperature=0.1
            )

            features_response = self.llm_client._text_understanding(features_request)
            features_content = features_response.content.strip()

            # 解析共性特征结果
            try:
                if features_content.startswith("```json"):
                    features_content = features_content[7:]
                if features_content.endswith("```"):
                    features_content = features_content[:-3]
                features_content = features_content.strip()
                common_features = json.loads(features_content)
                logger.info(f"成功提取视频共性特征：{json.dumps(common_features, ensure_ascii=False)[:200]}...")
            except json.JSONDecodeError as e:
                logger.error(f"解析共性特征失败: {str(e)}, 原始内容: {features_content}")
                common_features = {}

            # 第二步：基于共性特征提取因子
            logger.info("第二步：调用大模型提取共性因子")
            factors_prompt = prompt_manager.get_common_factors_extraction_prompt(
                report_count=len(reports),
                reports=json.dumps(reports, ensure_ascii=False, indent=2),
                common_features=json.dumps(common_features, ensure_ascii=False, indent=2)
            )

            # 调用大模型提取因子
            request = TextUnderstandingRequest(
                prompt=factors_prompt,
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

                # 使用模板校验结果
                factor_schema = prompt_manager.get_factor_template()
                is_valid, error_msg = validate_with_schema(factors, factor_schema)
                if is_valid:
                    logger.info("因子数据通过schema校验")
                else:
                    logger.warning(f"因子数据未通过schema校验: {error_msg}，但仍会返回结果")

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
        # 加载并填充提示词
        try:
            # 只传前3个报告节省token
            prompt = prompt_manager.get_strategy_generation_prompt(
                report_count=len(reports),
                factor_count=len(factors),
                reports=json.dumps(reports[:3], ensure_ascii=False, indent=2),
                factors=json.dumps(factors, ensure_ascii=False, indent=2)
            )
        except Exception as e:
            logger.error(f"加载生成策略提示词失败: {str(e)}")
            return {}

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

                # 使用模板校验结果
                strategy_schema = prompt_manager.get_strategy_template()
                is_valid, error_msg = validate_with_schema(strategy, strategy_schema)
                if is_valid:
                    logger.info("策略数据通过schema校验")
                else:
                    logger.warning(f"策略数据未通过schema校验: {error_msg}，但仍会返回结果")

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
