"""Agent模块使用示例"""
import os
import sys
from typing import Dict, Any

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.v1.app.agent import (
    ReActAgent,
    BaseTool,
    register_tool
)

# 自定义工具示例
@register_tool
class CalculatorTool(BaseTool):
    """计算器工具"""
    name = "calculator"
    description = "进行数学计算，支持加减乘除四则运算"
    parameters_schema = {
        "type": "object",
        "properties": {
            "expression": {"type": "string", "description": "数学表达式，如 '1 + 2 * 3'"}
        },
        "required": ["expression"]
    }

    def execute(self, parameters: Dict[str, Any]) -> str:
        try:
            expression = parameters["expression"]
            # 简单计算，生产环境请使用更安全的方式
            result = eval(expression)
            return f"计算结果: {expression} = {result}"
        except Exception as e:
            return f"计算失败: {str(e)}"

@register_tool
class TodoListTool(BaseTool):
    """待办事项管理工具"""
    name = "todo_list"
    description = "管理待办事项，支持添加、查询、删除功能"
    parameters_schema = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["add", "list", "delete"], "description": "操作类型"},
            "content": {"type": "string", "description": "待办内容，add时必填"},
            "index": {"type": "integer", "description": "待办索引，delete时必填"}
        },
        "required": ["action"]
    }

    def __init__(self):
        self.todos = []

    def execute(self, parameters: Dict[str, Any]) -> str:
        action = parameters["action"]

        if action == "add":
            content = parameters.get("content")
            if not content:
                return "添加失败：待办内容不能为空"
            self.todos.append(content)
            return f"添加成功：{content}，当前共有{len(self.todos)}条待办"

        elif action == "list":
            if not self.todos:
                return "待办列表为空"
            result = "待办列表：\n"
            for i, todo in enumerate(self.todos, 1):
                result += f"{i}. {todo}\n"
            return result

        elif action == "delete":
            index = parameters.get("index", 0) - 1
            if 0 <= index < len(self.todos):
                deleted = self.todos.pop(index)
                return f"删除成功：{deleted}"
            return "删除失败：索引无效"

        else:
            return f"不支持的操作：{action}"

def main():
    print("=== Agent使用示例 ===")

    # 1. 创建Agent
    agent = ReActAgent(
        agent_id="demo_agent_001",
        name="演示助手",
        description="这是一个演示用的智能助手，支持计算和待办事项管理。",
        max_iterations=3
    )

    # 2. 注册工具
    calculator = CalculatorTool()
    todo_tool = TodoListTool()
    agent.tool_system.register_tool(calculator)
    agent.tool_system.register_tool(todo_tool)

    print(f"\n已注册工具: {agent.tool_system.list_tools()}")

    # 3. 测试直接回答
    print("\n--- 测试1：直接回答 ---")
    result = agent.run("介绍一下你自己")
    print(f"回答: {result['answer']}")
    print(f"迭代次数: {result['iterations']}")
    print(f"耗时: {result['time_cost']:.2f}s")

    # 4. 测试工具调用 - 计算器
    print("\n--- 测试2：计算器工具 ---")
    result = agent.run("计算 123 + 456 * 2")
    print(f"回答: {result['answer']}")
    print(f"迭代次数: {result['iterations']}")

    # 5. 测试工具调用 - 待办事项
    print("\n--- 测试3：待办事项工具 ---")
    result = agent.run("帮我添加待办：购买牛奶")
    print(f"回答: {result['answer']}")

    result = agent.run("帮我添加待办：写代码")
    print(f"回答: {result['answer']}")

    result = agent.run("查看我的待办列表")
    print(f"回答: {result['answer']}")

    # 6. 测试私有资产
    print("\n--- 测试4：私有资产 ---")
    agent.asset_store.save("user_info", {
        "name": "张三",
        "email": "zhangsan@example.com",
        "preferences": {
            "theme": "dark",
            "notifications": True
        }
    })

    user_info = agent.asset_store.load("user_info")
    print(f"用户名称: {user_info['name']}")
    print(f"用户邮箱: {user_info['email']}")

    # 7. 测试记忆系统
    print("\n--- 测试5：记忆系统 ---")
    memories = agent.memory.get_recent(5)
    print(f"当前记忆条数: {len(memories)}")

    print("\n=== 演示结束 ===")

if __name__ == "__main__":
    main()
