"""Agent推理轨迹模型"""
import datetime
import json
from sqlalchemy import String, Text, BigInteger, DateTime, func, JSON, Boolean, Float
from sqlalchemy.orm import Mapped, mapped_column
from backend.store.database.async_database import Base


class AgentTrace(Base):
    """Agent推理轨迹表，存储所有Agent的推理过程信息"""
    __tablename__ = "agent_traces"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # 基础信息
    session_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False, comment="会话ID")
    user_id: Mapped[int | None] = mapped_column(BigInteger, index=True, nullable=True, comment="用户ID")
    project_id: Mapped[int | None] = mapped_column(BigInteger, index=True, nullable=True, comment="项目ID")

    # 请求信息
    user_input: Mapped[str] = mapped_column(Text, nullable=False, comment="用户输入内容")
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False, comment="系统提示词")

    # 模型信息
    model: Mapped[str] = mapped_column(String(64), nullable=False, comment="使用的模型名称")
    temperature: Mapped[float] = mapped_column(Float, nullable=False, comment="模型温度参数")
    max_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="最大生成长度")
    top_p: Mapped[float] = mapped_column(Float, nullable=False, comment="核采样参数")

    # 推理过程信息
    messages_history: Mapped[dict | list] = mapped_column(JSON, nullable=False, comment="完整的消息历史")
    iterations: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, comment="推理迭代次数")
    tool_calls: Mapped[list | None] = mapped_column(JSON, nullable=True, comment="所有工具调用信息")
    tool_results: Mapped[list | None] = mapped_column(JSON, nullable=True, comment="所有工具返回结果")

    # 结果信息
    final_answer: Mapped[str] = mapped_column(Text, nullable=True, comment="最终回答内容")
    cost_time: Mapped[float] = mapped_column(Float, nullable=False, comment="执行耗时(秒)")
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="是否执行成功")
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True, comment="错误信息")

    # 扩展信息
    meta_data: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="扩展元数据")

    # 时间信息
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="创建时间"
    )

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "project_id": self.project_id,
            "user_input": self.user_input,
            "system_prompt": self.system_prompt,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "messages_history": self.messages_history,
            "iterations": self.iterations,
            "tool_calls": self.tool_calls,
            "tool_results": self.tool_results,
            "final_answer": self.final_answer,
            "cost_time": self.cost_time,
            "success": self.success,
            "error_msg": self.error_msg,
            "metadata": self.meta_data,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
