# backend/v1/app/search/processors/retrieval/channels/http_api_channel.py
from typing import List, Optional, Dict, Any
import logging
import aiohttp
from ....core.interfaces import SearchChannel
from ....core.models import SearchQuery, SearchResult

logger = logging.getLogger(__name__)

class HttpApiChannel(SearchChannel):
    """外部HTTP API检索渠道"""

    def __init__(self, config: Dict[str, Any]):
        """
        初始化HTTP API渠道
        :param config: 渠道配置
        """
        self.config = config
        self.endpoint = config["endpoint"]
        self.api_key = config.get("api_key")
        self.timeout = config.get("timeout", 15)
        self.weight = config.get("weight", 0.7)

    @property
    def channel_name(self) -> str:
        return "http_api"

    @property
    def channel_type(self) -> str:
        return "http_api"

    def search(self, query: SearchQuery, context: Optional[Dict[str, Any]] = None) -> List[SearchResult]:
        """同步检索（使用requests）"""
        try:
            import requests
            headers = self._build_headers()
            payload = self._build_payload(query)

            response = requests.post(
                self.endpoint,
                json=payload,
                headers=headers,
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()

            return self._convert_to_search_results(data)
        except Exception as e:
            logger.error(f"HTTP API检索失败: {str(e)}", exc_info=True)
            return []

    async def asearch(self, query: SearchQuery, context: Optional[Dict[str, Any]] = None) -> List[SearchResult]:
        """异步检索（推荐）"""
        try:
            headers = self._build_headers()
            payload = self._build_payload(query)

            timeout = aiohttp.ClientTimeout(total=self.timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    self.endpoint,
                    json=payload,
                    headers=headers
                ) as response:
                    response.raise_for_status()
                    data = await response.json()

                    return self._convert_to_search_results(data)
        except Exception as e:
            logger.error(f"HTTP API异步检索失败: {str(e)}", exc_info=True)
            return []

    def health_check(self) -> bool:
        """健康检查"""
        try:
            import requests
            # 简单的GET请求检查服务是否可用
            response = requests.get(self.endpoint.replace("/search", "/health"), timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"HTTP API健康检查失败: {str(e)}")
            return False

    def _build_headers(self) -> Dict[str, str]:
        """构建请求头"""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "VidMuse-Search-Engine/1.0"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _build_payload(self, query: SearchQuery) -> Dict[str, Any]:
        """构建请求参数"""
        return {
            "query": query.query_text,
            "limit": query.top_k,
            "filters": query.filters,
            "metadata": query.metadata
        }

    def _convert_to_search_results(self, response_data: Dict) -> List[SearchResult]:
        """
        将API响应转换为统一的SearchResult格式
        :param response_data: API返回的JSON数据
        :return: SearchResult列表
        """
        results = []
        try:
            raw_results = response_data.get("results", [])
            for item in raw_results:
                score = float(item.get("score", 0.5)) * self.weight

                result = SearchResult(
                    result_id=str(item.get("id", "")),
                    content=str(item.get("content", "")),
                    score=score,
                    source=self.channel_name,
                    source_type=item.get("type", "external"),
                    metadata=item
                )
                results.append(result)
        except Exception as e:
            logger.error(f"解析API响应失败: {str(e)}", exc_info=True)

        return results
