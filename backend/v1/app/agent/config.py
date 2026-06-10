"""Agent模块配置"""
import os
from pathlib import Path

# 基础路径配置
BASE_DIR = Path(__file__).parent.parent.parent.parent.resolve()
DATA_DIR = BASE_DIR / "data" / "agent"

AGENT_CONFIG = {
    # 模型配置
    "model": {
        "default_model": os.getenv("DOUBAO_SEED", "doubao-seed"),
        "temperature": 0.7,
        "max_tokens": 2048,
        "top_p": 0.95
    },

    # ReAct流程配置
    "react": {
        "max_iterations": 5,  # 最大思考迭代次数
    },

    # 记忆系统配置
    "memory": {
        "max_short_term_length": 50,  # 短期记忆最大长度
        "long_term_embedding_model": os.getenv("EMBEDDING_MODEL", "bge-large-zh"),
    },


    # 上下文构建配置
    "context": {
        "template_dir": str(BASE_DIR / "v1" / "app" / "agent" / "templates"),
        "max_context_length": 8192,  # 最大上下文长度
    },

    # 链路追踪配置
    "tracing": {
        "enabled": True,
        "async_save": True,
        "save_system_prompt": True,
    }
}

# 确保数据目录存在
os.makedirs(AGENT_CONFIG["context"]["template_dir"], exist_ok=True)
