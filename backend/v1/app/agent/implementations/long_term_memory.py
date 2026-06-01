"""长期记忆实现（Stub版本）"""
import uuid
import json
import os
from typing import Any, Dict, List, Optional
from datetime import datetime
from ..core.memory import BaseLongTermMemory
from ..config import AGENT_CONFIG

class LongTermMemory(BaseLongTermMemory):
    """
    长期记忆实现（当前为Stub版本，使用文件系统存储）
    未来可以扩展为向量数据库存储，支持语义检索
    """

    def __init__(self, storage_path: Optional[str] = None, embedding_model: Optional[str] = None):
        """
        初始化长期记忆
        :param storage_path: 存储路径，默认使用配置中的值
        :param embedding_model: 向量模型名称，默认使用配置中的值
        """
        self.storage_path = storage_path or os.path.join(
            AGENT_CONFIG["asset"]["base_storage_path"], "long_term_memory"
        )
        self.embedding_model = embedding_model or AGENT_CONFIG["memory"]["long_term_embedding_model"]

        # 确保存储目录存在
        os.makedirs(self.storage_path, exist_ok=True)
        self._index_file = os.path.join(self.storage_path, "index.json")

        # 加载索引
        self._index = self._load_index()

    def _load_index(self) -> Dict[str, Dict[str, Any]]:
        """加载记忆索引"""
        if os.path.exists(self._index_file):
            with open(self._index_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save_index(self) -> None:
        """保存记忆索引"""
        with open(self._index_file, "w", encoding="utf-8") as f:
            json.dump(self._index, f, ensure_ascii=False, indent=2)

    def add(self, content: Any, metadata: Optional[Dict[str, Any]] = None) -> str:
        memory_id = str(uuid.uuid4())
        memory_item = {
            "id": memory_id,
            "content": content,
            "metadata": metadata or {},
            "timestamp": datetime.now().timestamp(),
            "created_at": datetime.now().isoformat()
        }

        # 保存记忆内容到文件
        memory_file = os.path.join(self.storage_path, f"{memory_id}.json")
        with open(memory_file, "w", encoding="utf-8") as f:
            json.dump(memory_item, f, ensure_ascii=False, indent=2)

        # 更新索引
        self._index[memory_id] = {
            "id": memory_id,
            "content_preview": str(content)[:100],  # 预览内容，用于简单搜索
            "metadata": metadata or {},
            "timestamp": memory_item["timestamp"],
            "file_path": memory_file
        }
        self._save_index()

        return memory_id

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        简单的关键词搜索实现
        未来将替换为向量语义检索
        """
        results = []
        query_lower = query.lower()

        # 按时间倒序搜索
        sorted_memories = sorted(
            self._index.values(),
            key=lambda x: x["timestamp"],
            reverse=True
        )

        for memory_meta in sorted_memories:
            if query_lower in memory_meta["content_preview"].lower():
                # 加载完整记忆内容
                memory_file = memory_meta["file_path"]
                if os.path.exists(memory_file):
                    with open(memory_file, "r", encoding="utf-8") as f:
                        memory_item = json.load(f)
                        results.append(memory_item)
                        if len(results) >= top_k:
                            break

        return results

    def get_recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近的记忆"""
        results = []
        sorted_memories = sorted(
            self._index.values(),
            key=lambda x: x["timestamp"],
            reverse=True
        )[:limit]

        for memory_meta in sorted_memories:
            memory_file = memory_meta["file_path"]
            if os.path.exists(memory_file):
                with open(memory_file, "r", encoding="utf-8") as f:
                    memory_item = json.load(f)
                    results.append(memory_item)

        return results

    def clear(self) -> None:
        """清空所有长期记忆"""
        # 删除所有记忆文件
        for memory_meta in self._index.values():
            if os.path.exists(memory_meta["file_path"]):
                os.remove(memory_meta["file_path"])

        # 清空索引
        self._index.clear()
        self._save_index()

    def delete(self, memory_id: str) -> bool:
        """删除指定记忆"""
        if memory_id not in self._index:
            return False

        memory_meta = self._index[memory_id]
        if os.path.exists(memory_meta["file_path"]):
            os.remove(memory_meta["file_path"])

        del self._index[memory_id]
        self._save_index()
        return True

    def exists(self, memory_id: str) -> bool:
        """检查记忆是否存在"""
        return memory_id in self._index
