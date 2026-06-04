# backend/tests/search/test_config.py
import pytest
from backend.v1.app.search.config import SearchConfig

def test_default_config():
    """测试默认配置"""
    config = SearchConfig()

    assert config.DEFAULT_TOP_K == 10
    assert config.DEFAULT_TIMEOUT == 30
    assert config.FAIL_FAST is False
    assert isinstance(config.ENABLED_CHANNELS, list)
    assert isinstance(config.CHANNEL_CONFIG, dict)
    assert isinstance(config.ENABLED_QUERY_PROCESSORS, list)
    assert isinstance(config.ENABLED_POST_PROCESSORS, list)

def test_config_from_dict():
    """测试从字典加载配置"""
    custom_config = {
        "DEFAULT_TOP_K": 20,
        "DEFAULT_TIMEOUT": 60,
        "ENABLED_CHANNELS": ["vector_db", "mysql"],
        "CHANNEL_CONFIG": {
            "vector_db": {"enabled": True, "collection": "test"}
        }
    }

    config = SearchConfig.from_dict(custom_config)

    assert config.DEFAULT_TOP_K == 20
    assert config.DEFAULT_TIMEOUT == 60
    assert config.ENABLED_CHANNELS == ["vector_db", "mysql"]
    assert config.CHANNEL_CONFIG["vector_db"]["collection"] == "test"
