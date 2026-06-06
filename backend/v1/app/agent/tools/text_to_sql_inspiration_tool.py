"""灵感模板模块TextToSQL查询工具"""
from typing import Dict, Any, List
import json
import logging
import re
import asyncio

from backend.store.database.async_database import get_db
from ..core.tool import BaseTool
from ..utils.tool_registry import register_tool
from backend.v1.app.pipeline.services.llm_service import LLMService
from backend.providers.dto.schema import TextUnderstandingRequest

logger = logging.getLogger(__name__)


@register_tool
class TextToSQLInspirationTool(BaseTool):
    """
    灵感模板模块自然语言查询工具，支持通过自然语言查询创作因子、创作策略、灵感模板等相关数据
    """
    name: str = "text_to_sql_inspiration"
    description: str = "灵感模板模块自然语言查询工具，支持通过自然语言查询创作因子、创作策略、灵感模板等相关数据"
    parameters_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "自然语言查询问题，例如：'查询流行度大于0.8的创作因子'、'查找成功率最高的前5个创作策略'"
            },
            "limit": {
                "type": "integer",
                "description": "返回结果数量限制，默认返回10条",
                "default": 10
            }
        },
        "required": ["query"]
    }

    # 允许查询的表
    ALLOWED_TABLES = {
        "factors", "strategies", "inspiration_templates", "template_factor_relations"
    }

    # 危险关键字
    DANGEROUS_KEYWORDS = {
        "DROP", "ALTER", "DELETE", "INSERT", "UPDATE", "TRUNCATE", "REPLACE",
        "CREATE", "EXEC", "EXECUTE", "UNION", "GRANT", "REVOKE", "SHOW", "DESCRIBE"
    }

    # 表结构信息，用于提示词
    TABLE_SCHEMAS = {
        "factors": """
表名: factors (创作因子表)
字段:
- id: 主键ID
- factor_id: 全局唯一因子ID
- factor_type: 因子类型：content_structure/product_expression/user_operation
- name: 因子名称
- description: 因子详细描述
- applicable_scenarios: 适用场景列表(JSON数组)
- data_schema: 因子数据结构定义(JSON)
- example: 因子示例数据(JSON)
- tags: 标签列表(JSON数组)
- popularity: 流行度，0-1之间的浮点数
- usage_count: 使用次数统计
- is_deleted: 是否删除：0-未删除，1-已删除
- created_at: 创建时间
- updated_at: 更新时间
""",
        "strategies": """
表名: strategies (创作策略表)
字段:
- id: 主键ID
- strategy_id: 全局唯一策略ID
- name: 策略名称
- description: 策略详细描述
- applicable_scenarios: 适用场景列表(JSON数组)
- core_logic: 核心创作逻辑描述
- required_factor_types: 必填因子类型列表(JSON数组)
- optional_factor_types: 可选因子类型列表(JSON数组)
- combination_rules: 因子组合规则描述
- success_rate: 历史爆款成功率，0-1之间的浮点数
- tags: 标签列表(JSON数组)
- usage_count: 使用次数统计
- is_deleted: 是否删除：0-未删除，1-已删除
- created_at: 创建时间
- updated_at: 更新时间
""",
        "inspiration_templates": """
表名: inspiration_templates (灵感模板表)
字段:
- id: 主键ID
- template_id: 全局唯一模板ID
- strategy_id: 关联的策略ID
- name: 模板名称
- description: 模板描述
- combination_example: 完整组合示例(JSON)
- version: 版本号
- success_rate: 模板成功率，0-1之间的浮点数
- usage_count: 使用次数统计
- is_deleted: 是否删除：0-未删除，1-已删除
- created_at: 创建时间
- updated_at: 更新时间
""",
        "template_factor_relations": """
表名: template_factor_relations (模板-因子关联表)
字段:
- id: 主键ID
- template_id: 模板ID
- factor_id: 因子ID
- factor_usage_type: 因子使用类型：1-必填，2-可选
- sort_order: 排序权重
- created_at: 创建时间
"""
    }

    def __init__(self, config: Dict = None):
        super().__init__()
        self.llm_service = LLMService()
        self.config = config or {}

    def execute(self, parameters: Dict[str, Any]) -> str:
        """
        执行TextToSQL查询
        :param parameters: 查询参数，包含query和可选的limit
        :return: JSON格式的查询结果字符串
        """
        try:
            # 获取参数
            query = parameters.get("query", "").strip()
            limit = parameters.get("limit", 10)

            if not query:
                return json.dumps({
                    "error": "参数错误",
                    "message": "查询内容不能为空"
                }, ensure_ascii=False)

            # 生成SQL
            sql = self._generate_sql(query, limit)
            if not sql:
                return json.dumps({
                    "error": "生成SQL失败",
                    "message": "无法根据您的查询生成有效的SQL语句"
                }, ensure_ascii=False)

            # 验证SQL安全性
            validation_result = self._validate_sql(sql)
            if not validation_result["valid"]:
                return json.dumps({
                    "error": "SQL验证失败",
                    "message": validation_result["message"],
                    "generated_sql": sql
                }, ensure_ascii=False)

            # 执行SQL
            result = asyncio.run(self._execute_sql(sql, limit))

            return json.dumps({
                "success": True,
                "query": query,
                "generated_sql": sql,
                "data": result
            }, ensure_ascii=False, default=str)

        except Exception as e:
            logger.error(f"TextToSQL查询失败: {str(e)}", exc_info=True)
            return json.dumps({
                "error": "查询失败",
                "message": str(e)
            }, ensure_ascii=False)

    def _generate_sql(self, query: str, limit: int) -> str:
        """
        使用大模型生成SQL语句
        :param query: 自然语言查询
        :param limit: 结果数量限制
        :return: 生成的SQL语句
        """
        # 构造提示词
        schema_info = "\n".join(self.TABLE_SCHEMAS.values())

        prompt = f"""
你是一个专业的SQL生成助手，专门为灵感模板模块生成安全的SQL查询语句。

## 数据库表结构
{schema_info}

## 生成规则
1. 只能生成SELECT查询语句，绝对禁止生成任何修改数据的语句（INSERT/UPDATE/DELETE/DROP/ALTER等）
2. 只能查询上面列出的4张表，不允许访问其他任何表
3. 自动过滤已删除数据：对于factors、strategies、inspiration_templates表，必须添加WHERE is_deleted = 0条件
4. 生成的SQL要简洁高效，避免不必要的复杂关联
5. 如果需要关联查询，使用合理的JOIN条件
6. 结果只返回SQL语句本身，不要有任何其他解释性文字，不要用markdown格式包裹
7. 不要在SQL中包含LIMIT子句，系统会自动添加
8. 字段名和表名要严格按照上面的定义使用，不要拼写错误

## 用户查询
{query}

请直接返回符合要求的SQL语句：
"""

        try:
            # 调用大模型
            request = TextUnderstandingRequest(
                prompt=prompt,
                text="请根据用户的自然语言查询生成符合要求的SQL语句，只返回SQL本身",
                max_tokens=500,
                temperature=0.1
            )

            response = self.llm_service.llm_client._text_understanding(request)
            sql = response.content.strip()

            # 清理可能的markdown代码块标记
            if sql.startswith("```sql"):
                sql = sql[6:]
            if sql.startswith("```"):
                sql = sql[3:]
            if sql.endswith("```"):
                sql = sql[:-3]

            sql = sql.strip().rstrip(';')  # 去掉结尾的分号，方便后面加LIMIT

            return sql

        except Exception as e:
            logger.error(f"生成SQL失败: {str(e)}", exc_info=True)
            return ""

    def _validate_sql(self, sql: str) -> Dict[str, Any]:
        """
        验证SQL语句的安全性和合法性
        :param sql: 生成的SQL语句
        :return: 验证结果，包含valid字段和message字段
        """
        # 转换为大写便于检查关键字
        sql_upper = sql.upper()

        # 1. 必须以SELECT开头
        if not sql_upper.startswith("SELECT"):
            return {
                "valid": False,
                "message": "只能执行SELECT查询操作"
            }

        # 2. 检查危险关键字，确保是独立的单词
        for keyword in self.DANGEROUS_KEYWORDS:
            # 使用正则表达式匹配独立的关键字，避免匹配到字段名或表名中的子字符串
            pattern = r"\b" + re.escape(keyword) + r"\b"
            if re.search(pattern, sql_upper):
                return {
                    "valid": False,
                    "message": f"SQL包含危险关键字: {keyword}"
                }

        # 3. 检查查询的表是否在允许列表中
        # 简单实现：提取FROM后面的表名
        from_match = re.search(r"FROM\s+([a-zA-Z0-9_]+)", sql_upper)
        if from_match:
            table_name = from_match.group(1).lower()
            if table_name not in self.ALLOWED_TABLES:
                return {
                    "valid": False,
                    "message": f"不允许查询表: {table_name}"
                }

        # 检查JOIN的表
        join_matches = re.findall(r"JOIN\s+([a-zA-Z0-9_]+)", sql_upper)
        for join_table in join_matches:
            join_table = join_table.lower()
            if join_table not in self.ALLOWED_TABLES:
                return {
                    "valid": False,
                    "message": f"不允许关联查询表: {join_table}"
                }

        # 4. 检查是否包含is_deleted条件（对于需要的表）
        if "factors" in sql.lower() and "IS_DELETED" not in sql_upper:
            logger.warning("SQL查询factors表但未包含is_deleted条件，自动添加")

        if "strategies" in sql.lower() and "IS_DELETED" not in sql_upper:
            logger.warning("SQL查询strategies表但未包含is_deleted条件，自动添加")

        if "inspiration_templates" in sql.lower() and "IS_DELETED" not in sql_upper:
            logger.warning("SQL查询inspiration_templates表但未包含is_deleted条件，自动添加")

        return {
            "valid": True,
            "message": "验证通过"
        }

    async def _execute_sql(self, sql: str, limit: int) -> List[Dict[str, Any]]:
        """
        执行SQL查询
        :param sql: SQL语句
        :param limit: 结果数量限制
        :return: 查询结果列表
        """
        # 自动添加LIMIT
        sql_with_limit = f"{sql} LIMIT {limit}"

        async for db in get_db():
            try:
                # 执行查询
                result = await db.fetch_all(sql_with_limit)
                # 转换为字典列表
                return [dict(row) for row in result]
            except Exception as e:
                logger.error(f"执行SQL失败: {str(e)}, SQL: {sql_with_limit}")
                raise
