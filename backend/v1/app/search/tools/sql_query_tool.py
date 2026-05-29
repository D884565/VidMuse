from typing import Dict, Any, List
from .base import BaseSearchTool
from ..core import Document
from ..retrieval.channels.mysql_channel import MySQLChannel
from ..config import DATA_SOURCE_CONFIG


class SQLQueryTool(BaseSearchTool):
    """
    SQL查询工具，直接执行SQL查询获取结构化数据
    适合查询统计数据、列表数据、用户信息等结构化信息
    """
    name = "sql_query"
    description = "执行SQL查询从关系型数据库中获取结构化数据。" \
                  "适用于：统计查询、数据列表查询、用户信息查询、数值计算等需要结构化数据的场景。" \
                  "当问题需要统计总数、平均值、最大值、列表数据等信息时使用此工具。"
    parameters_schema = {
        "type": "object",
        "properties": {
            "sql": {
                "type": "string",
                "description": "要执行的SQL查询语句，只能是SELECT查询，不能包含修改数据的语句"
            },
            "params": {
                "type": "array",
                "description": "SQL查询的参数列表，用于替换SQL中的占位符",
                "default": []
            },
            "database": {
                "type": "string",
                "description": "要查询的数据库名称，默认使用系统配置的数据库",
                "default": "default"
            }
        },
        "required": ["sql"]
    }

    # SQL查询不使用通用检索流程
    default_retrieval_type = "sql"

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.default_db_config = DATA_SOURCE_CONFIG.get("mysql", {})
        self.connection_error = None

        # 初始化MySQL通道（延迟连接，实际使用时再连接）
        self._mysql_channel = None

    @property
    def mysql_channel(self):
        """懒加载数据库连接"""
        if self._mysql_channel is None and self.connection_error is None:
            try:
                self._mysql_channel = MySQLChannel(self.default_db_config)
                self._mysql_channel.connect()
            except Exception as e:
                self.connection_error = str(e)
        return self._mysql_channel

    def execute(self, params: Dict[str, Any]) -> str:
        """执行SQL查询（模板实现，具体逻辑后续补充）"""
        if self.connection_error:
            return f"数据库连接失败：{self.connection_error}"

        sql = params.get("sql", "").strip()
        sql_params = params.get("params", [])
        database = params.get("database", "default")

        if not sql:
            return "错误：SQL语句不能为空"

        # 安全检查，只允许SELECT查询
        if not sql.lower().startswith("select"):
            return "错误：只允许执行SELECT查询语句，不允许修改数据"

        try:
            # 执行SQL查询
            documents = self.mysql_channel.execute_query(sql, tuple(sql_params) if sql_params else None)

            if not documents:
                return "查询结果为空"

            # 格式化结果
            return self._format_sql_results(documents)

        except Exception as e:
            return f"SQL查询执行失败：{str(e)}"

    def _format_sql_results(self, documents: List[Document]) -> str:
        """SQL查询结果的专用格式化"""
        formatted_results = []
        for i, doc in enumerate(documents, 1):
            formatted_results.append(f"[{i}] {doc.content}")

        return "SQL查询结果：\n\n" + "\n---\n".join(formatted_results)
