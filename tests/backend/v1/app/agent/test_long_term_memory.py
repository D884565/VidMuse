import pytest
import tempfile
import os
from backend.v1.app.agent.implementations.long_term_memory import LongTermMemory

def test_long_term_memory_basic_operations():
    """测试长期记忆基本操作"""
    with tempfile.TemporaryDirectory() as temp_dir:
        memory = LongTermMemory(storage_path=temp_dir)

        # 添加记忆
        memory_id = memory.add("长期记忆测试内容", {"type": "test"})
        assert memory_id is not None

        # 检查存在
        assert memory.exists(memory_id) is True

        # 搜索
        results = memory.search("测试", top_k=5)
        assert len(results) >= 1

        # 删除
        assert memory.delete(memory_id) is True
        assert memory.exists(memory_id) is False
