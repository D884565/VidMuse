from typing import Dict, Any, List

# Agent配置
AGENT_CONFIG: Dict[str, Any] = {
    # 模型配置
    "model": {
        "name": "doubao-1.5-pro",  # 豆包模型名称
        "temperature": 0.7,        # 温度参数
        "max_tokens": 2000,        # 最大生成token数
        "top_p": 0.9,              # top_p参数
    },

    # 工具配置
    "tools": {
        "enabled": ["rag_search"],  # 启用的工具列表
        "rag_search": {
            "default_top_k": 10,    # RAG检索默认返回数量
            "max_top_k": 20,        # 最大返回数量
        }
    },

    # 会话配置
    "session": {
        "timeout": 3600,           # 会话超时时间（秒），1小时
        "max_history_length": 20,  # 最大历史消息数
        "cleanup_interval": 300,   # 过期会话清理间隔（秒）
    },

    # 系统提示词
    "system_prompt": """你是一个智能助手，能够回答用户的问题。如果问题涉及到知识库内容，请使用rag_search工具查询相关信息，然后基于查询结果回答用户的问题。
如果无法通过工具获取答案，可以直接回答用户的问题，但要说明信息可能不是最新的。
回答要简洁、准确，避免冗余信息。""",
}

# 工具定义映射
TOOL_CLASS_MAPPING: Dict[str, str] = {
    "rag_search": "backend.v1.app.agent.tools.rag_tool.RAGSearchTool",
}
