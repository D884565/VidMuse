from typing import Dict, Any, List, Optional, Tuple
from .base import BaseSearchTool
from ..core import Document
from ..retrieval import SQLRetriever
from ..retrieval.channels.mysql_channel import MySQLChannel
from ..config import DATA_SOURCE_CONFIG


class SQLQueryTool(BaseSearchTool):
    """
    SQL查询工具，直接执行SQL查询获取结构化数据
    适合查询统计数据、列表数据、用户信息等结构化信息
    """

    @property
    def name(self) -> str:
        return "sql_query"

    @property
    def description(self) -> str:
        return "执行SQL查询从关系型数据库中获取结构化数据。" \
               "适用于：统计查询、数据列表查询、用户信息查询、数值计算等需要结构化数据的场景。" \
               "当问题需要统计总数、平均值、最大值、列表数据等信息时使用此工具。"

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
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

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.default_db_config = DATA_SOURCE_CONFIG.get("mysql", {})

        # 初始化MySQL通道
        self.mysql_channel = MySQLChannel(self.default_db_config)
        try:
            self.mysql_channel.connect()
        except Exception as e:
            self.connection_error = str(e)
        else:
            self.connection_error = None

    def execute(self, params: Dict[str, Any]) -> str:
        """执行SQL查询"""
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
            formatted_results = []
            for i, doc in enumerate(documents, 1):
                formatted_results.append(
                    f"[{i}] {doc.content}"
                )

            return "SQL查询结果：\n\n" + "\n---\n".join(formatted_results)

        except Exception as e:
            return f"SQL查询执行失败：{str(e)}"
