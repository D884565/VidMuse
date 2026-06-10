"""短期记忆实现"""
import uuid
import time
from typing import Any, Dict, List, Optional
from datetime import datetime
from ..core.memory import BaseShortTermMemory
from ..config import AGENT_CONFIG

class ShortTermMemory(BaseShortTermMemory):
    """
    短期记忆实现，存储在内存中，会话结束后清除
    适合存储会话历史、中间思考结果等临时信息
    """

    def __init__(self, max_length: Optional[int] = None):
        """
        初始化短期记忆
        :param max_length: 最大记忆条数，默认使用配置中的值
        """
        self.max_length = max_length or AGENT_CONFIG["memory"]["max_short_term_length"]
        self._memories: List[Dict[str, Any]] = []

    def add(self, content: Any, metadata: Optional[Dict[str, Any]] = None) -> str:
        memory_id = str(uuid.uuid4())
        memory_item = {
            "id": memory_id,
            "content": content,
            "metadata": metadata or {},
            "timestamp": time.time(),
            "created_at": datetime.now().isoformat()
        }

        self._memories.insert(0, memory_item)

        # 超过最大长度时截断
        if len(self._memories) > self.max_length:
            self._memories = self._memories[:self.max_length]

        return memory_id

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        简单的关键词搜索实现
        复杂场景可以替换为向量检索
        """
        results = []
        query_lower = query.lower()

        for memory in self._memories:
            content_str = str(memory["content"]).lower()
            if query_lower in content_str:
                results.append(memory)
                if len(results) >= top_k:
                    break

        return results

    def get_recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        limit = min(limit, len(self._memories))
        return self._memories[:limit].copy()

    def clear(self) -> None:
        self._memories.clear()

    def delete(self, memory_id: str) -> bool:
        for i, memory in enumerate(self._memories):
            if memory["id"] == memory_id:
                del self._memories[i]
                return True
        return False

    def exists(self, memory_id: str) -> bool:
        """检查记忆是否存在"""
        return any(memory["id"] == memory_id for memory in self._memories)

    def __len__(self) -> int:
        return len(self._memories)
