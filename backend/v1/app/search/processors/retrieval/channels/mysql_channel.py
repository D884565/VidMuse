# backend/v1/app/search/processors/retrieval/channels/mysql_channel.py
from typing import List, Optional, Dict, Any
import logging
from sqlalchemy import text
from ....core.interfaces import SearchChannel
from ....core.models import SearchQuery, SearchResult
from backend.store.database.sync_database import get_db

logger = logging.getLogger(__name__)

class MySQLChannel(SearchChannel):
    """MySQL关系型数据库检索渠道"""

    def __init__(self, config: Dict[str, Any]):
        """
        初始化MySQL渠道
        :param config: 渠道配置
        """
        self.config = config
        self.table_name = config["table"]
        self.search_fields = config["search_fields"]  # 要搜索的字段列表
        self.weight = config.get("weight", 0.8)
        self.db_session = next(get_db())

    @property
    def channel_name(self) -> str:
        return "mysql"

    @property
    def channel_type(self) -> str:
        return "mysql"

    def search(self, query: SearchQuery, context: Optional[Dict[str, Any]] = None) -> List[SearchResult]:
        """同步检索"""
        try:
            # 构建搜索SQL
            sql, params = self._build_search_sql(query)

            # 执行查询
            result = self.db_session.execute(text(sql), params)
            rows = result.mappings().all()

            # 转换为统一结果格式
            return self._convert_to_search_results(rows)
        except Exception as e:
            logger.error(f"MySQL检索失败: {str(e)}", exc_info=True)
            return []

    async def asearch(self, query: SearchQuery, context: Optional[Dict[str, Any]] = None) -> List[SearchResult]:
        """异步检索"""
        import asyncio
        return await asyncio.to_thread(self.search, query, context)

    def health_check(self) -> bool:
        """健康检查"""
        try:
            self.db_session.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"MySQL健康检查失败: {str(e)}")
            return False

    def _build_search_sql(self, query: SearchQuery) -> tuple[str, Dict[str, Any]]:
        """
        构建搜索SQL语句
        :param query: 检索查询
        :return: (SQL语句, 参数)
        """
        # 构建WHERE条件
        conditions = []
        params = {"query": f"%{query.query_text}%", "limit": query.top_k}

        # 全文搜索条件
        search_conditions = [f"{field} LIKE :query" for field in self.search_fields]
        conditions.append(f"({ ' OR '.join(search_conditions) })")

        # 过滤条件
        if query.filters:
            for key, value in query.filters.items():
                conditions.append(f"{key} = :filter_{key}")
                params[f"filter_{key}"] = value

        # 构建完整SQL
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        sql = f"""
            SELECT *,
                MATCH({', '.join(self.search_fields)}) AGAINST(:query) as relevance_score
            FROM {self.table_name}
            WHERE {where_clause}
            ORDER BY relevance_score DESC
            LIMIT :limit
        """

        return sql, params

    def _convert_to_search_results(self, rows: List[Dict]) -> List[SearchResult]:
        """
        将MySQL查询结果转换为统一的SearchResult格式
        :param rows: MySQL查询结果行
        :return: SearchResult列表
        """
        results = []
        for row in rows:
            row_dict = dict(row)
            # 获取得分，优先使用relevance_score，没有的话默认0.5
            score = float(row_dict.get("relevance_score", 0.5)) * self.weight
            # 组合内容
            content_parts = [str(row_dict.get(field, "")) for field in self.search_fields]
            content = "\n".join(filter(None, content_parts))

            result = SearchResult(
                result_id=f"mysql_{row_dict.get('id', '')}",
                content=content,
                score=score,
                source=self.channel_name,
                source_type=self.config.get("source_type", "database"),
                metadata=row_dict
            )
            results.append(result)

        return results
