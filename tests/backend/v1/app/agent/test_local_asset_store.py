import pytest
import tempfile
import os
from backend.v1.app.agent.implementations.local_asset_store import LocalAssetStore

def test_asset_basic_operations():
    """测试资产基本操作"""
    with tempfile.TemporaryDirectory() as temp_dir:
        asset_store = LocalAssetStore(agent_id="test_agent", base_path=temp_dir)

        # 保存资产
        asset_store.save("config", {"api_key": "test_key", "timeout": 30}, {"version": "1.0"})
        asset_store.save("data/user_list", ["user1", "user2", "user3"])

        # 检查存在
        assert asset_store.exists("config") is True
        assert asset_store.exists("data/user_list") is True
        assert asset_store.exists("non_existent") is False

        # 加载资产
        config = asset_store.load("config")
        assert config["api_key"] == "test_key"
        assert config["timeout"] == 30

        user_list = asset_store.load("data/user_list")
        assert len(user_list) == 3
        assert "user1" in user_list

        # 获取元数据
        metadata = asset_store.get_metadata("config")
        assert metadata["version"] == "1.0"

        # 列出键
        keys = asset_store.list_keys()
        assert len(keys) == 2
        assert "config" in keys
        assert "data/user_list" in keys

        # 按前缀列出
        data_keys = asset_store.list_keys(prefix="data/")
        assert len(data_keys) == 1
        assert data_keys[0] == "data/user_list"

        # 删除资产
        assert asset_store.delete("config") is True
        assert asset_store.exists("config") is False

        # 加载不存在的资产，返回默认值
        non_existent = asset_store.load("non_existent", default="default_value")
        assert non_existent == "default_value"
