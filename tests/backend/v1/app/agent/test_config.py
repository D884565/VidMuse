import os
from backend.v1.app.agent.config import AGENT_CONFIG

def test_config_structure():
    """测试配置文件结构完整性"""
    required_keys = ["model", "react", "memory", "asset", "context", "tracing"]
    for key in required_keys:
        assert key in AGENT_CONFIG, f"缺少配置项: {key}"

    # 验证model配置
    assert "default_model" in AGENT_CONFIG["model"]
    assert "temperature" in AGENT_CONFIG["model"]
    assert "max_tokens" in AGENT_CONFIG["model"]
    assert "top_p" in AGENT_CONFIG["model"]

    # 验证react配置
    assert "max_iterations" in AGENT_CONFIG["react"]

    # 验证memory配置
    assert "max_short_term_length" in AGENT_CONFIG["memory"]

    # 验证asset配置
    assert "base_storage_path" in AGENT_CONFIG["asset"]
