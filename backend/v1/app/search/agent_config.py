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
    # ReAct配置
    "react": {
        "max_iterations": 5,       # 最大思考-行动迭代次数，防止无限循环
        "enable_parallel_tools": True,  # 是否启用并行工具调用
    },

    # 工具配置
    "tools": {
        "enabled": ["semantic_search", "keyword_search", "sql_query", "hybrid_search", "general_search"],  # 启用的工具列表
    },

    # 会话配置
    "session": {
        "timeout": 3600,           # 会话超时时间（秒），1小时
        "max_history_length": 20,  # 最大历史消息数
        "cleanup_interval": 300,   # 过期会话清理间隔（秒）
    },

    # 系统提示词
    "system_prompt": """你是一个智能助手，能够回答用户的问题。你可以使用以下工具来获取信息：
- semantic_search: 语义检索，适合查询概念、原理、知识类问题
- keyword_search: 关键词检索，适合查找特定信息、列表类问题
- sql_query: SQL查询，适合查询统计数据、结构化信息
- hybrid_search: 混合检索，适合复杂查询，同时考虑语义和关键词
- general_search: 通用检索，自动选择最合适的检索方式

如果问题涉及到知识库内容，请选择合适的工具查询相关信息，然后基于查询结果回答用户的问题。
如果无法通过工具获取答案，可以直接回答用户的问题，但要说明信息可能不是最新的。
回答要简洁、准确，避免冗余信息。""",
}
