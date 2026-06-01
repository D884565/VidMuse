import pytest
from backend.v1.app.agent.implementations.short_term_memory import ShortTermMemory

def test_add_and_get_recent():
    memory = ShortTermMemory(max_length=10)
    for i in range(5):
        memory_id = memory.add(f"记忆内容{i}", {"type": "test", "index": i})
        assert memory_id is not None
    recent = memory.get_recent(3)
    assert len(recent) == 3
    assert recent[0]["content"] == "记忆内容4"
    assert recent[1]["content"] == "记忆内容3"
    assert recent[2]["content"] == "记忆内容2"

def test_memory_truncation():
    memory = ShortTermMemory(max_length=3)
    for i in range(4):
        memory.add(f"记忆内容{i}")
    recent = memory.get_recent(10)
    assert len(recent) == 3
    assert recent[0]["content"] == "记忆内容3"
    assert recent[1]["content"] == "记忆内容2"
    assert recent[2]["content"] == "记忆内容1"

def test_search_memory():
    memory = ShortTermMemory()
    memory.add("Python是一种编程语言", {"type": "knowledge"})
    memory.add("Java是面向对象的语言", {"type": "knowledge"})
    memory.add("Python适合数据分析", {"type": "knowledge"})
    results = memory.search("Python", top_k=2)
    assert len(results) == 2
    assert any("Python" in res["content"] for res in results)

def test_clear_memory():
    memory = ShortTermMemory()
    memory.add("测试内容")
    assert len(memory.get_recent()) == 1
    memory.clear()
    assert len(memory.get_recent()) == 0

def test_delete_memory():
    memory = ShortTermMemory()
    memory_id = memory.add("要删除的内容")
    assert memory.exists(memory_id) is True
    result = memory.delete(memory_id)
    assert result is True
    assert memory.exists(memory_id) is False
