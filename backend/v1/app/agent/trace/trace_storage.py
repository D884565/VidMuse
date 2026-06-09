"""Agent推理轨迹存储模块
提供保存Agent推理轨迹的功能（同步版本，避免事件循环问题）
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from backend.store.database.sync_database import SessionLocal
from backend.v1.app.models.agent_trace import AgentTrace

logger = logging.getLogger(__name__)


class TraceStorage:
    """Agent推理轨迹存储类"""

    def save_trace(
        self,
        session_id: str,
        user_input: str,
        system_prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
        top_p: float,
        messages_history: List[Dict[str, Any]],
        iterations: int,
        tool_calls: List[Dict[str, Any]],
        tool_results: List[str],
        final_answer: str,
        cost_time: float,
        success: bool = True,
        error_msg: Optional[str] = None,
        user_id: Optional[int] = None,
        project_id: Optional[int] = None,
        meta_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """保存推理轨迹到数据库（同步）

        :param session_id: 会话ID
        :param user_input: 用户输入内容
        :param system_prompt: 系统提示词
        :param model: 使用的模型名称
        :param temperature: 模型温度参数
        :param max_tokens: 最大生成长度
        :param top_p: 核采样参数
        :param messages_history: 完整的消息历史
        :param iterations: 推理迭代次数
        :param tool_calls: 所有工具调用信息
        :param tool_results: 所有工具返回结果
        :param final_answer: 最终回答内容
        :param cost_time: 执行耗时(秒)
        :param success: 是否执行成功
        :param error_msg: 错误信息
        :param user_id: 用户ID
        :param project_id: 项目ID
        :param meta_data: 扩展元数据
        """
        db = SessionLocal()
        try:
            trace = AgentTrace(
                session_id=session_id,
                user_id=user_id,
                project_id=project_id,
                user_input=user_input,
                system_prompt=system_prompt,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                messages_history=messages_history,
                iterations=iterations,
                tool_calls=tool_calls if tool_calls else [],
                tool_results=tool_results if tool_results else [],
                final_answer=final_answer,
                cost_time=cost_time,
                success=success,
                error_msg=error_msg,
                meta_data=meta_data
            )
            db.add(trace)
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"保存Agent轨迹到数据库失败: {str(e)}")
            raise
        finally:
            db.close()


# 全局存储实例
trace_storage = TraceStorage()
