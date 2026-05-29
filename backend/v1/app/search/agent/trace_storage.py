"""Agent推理轨迹存储服务"""
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession, async_session
from sqlalchemy import select
from backend.v1.app.models.agent_trace import AgentTrace



class TraceStorage:
    """Agent推理轨迹存储类"""

    @staticmethod
    async def save_trace(
        session_id: str,
        user_input: str,
        system_prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
        top_p: float,
        messages_history: List[Dict[str, Any]],
        iterations: int,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        tool_results: Optional[List[str]] = None,
        final_answer: Optional[str] = None,
        cost_time: float = 0.0,
        success: bool = True,
        error_msg: Optional[str] = None,
        user_id: Optional[int] = None,
        project_id: Optional[int] = None,
        meta_data: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        保存Agent推理轨迹
        :return: 保存的轨迹ID
        """
        async with async_session() as session:
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
                tool_calls=tool_calls,
                tool_results=tool_results,
                final_answer=final_answer,
                cost_time=cost_time,
                success=success,
                error_msg=error_msg,
                meta_data=meta_data
            )
            session.add(trace)
            await session.commit()
            await session.refresh(trace)
            return trace.id

    @staticmethod
    async def get_trace_by_id(trace_id: int) -> Optional[AgentTrace]:
        """根据ID获取轨迹"""
        async with async_session() as session:
            result = await session.execute(select(AgentTrace).where(AgentTrace.id == trace_id))
            return result.scalar_one_or_none()

    @staticmethod
    async def get_traces_by_session_id(session_id: str, limit: int = 100) -> List[AgentTrace]:
        """根据会话ID获取轨迹列表"""
        async with async_session() as session:
            result = await session.execute(
                select(AgentTrace)
                .where(AgentTrace.session_id == session_id)
                .order_by(AgentTrace.created_at.desc())
                .limit(limit)
            )
            return list(result.scalars().all())

    @staticmethod
    async def get_traces_by_user_id(user_id: int, limit: int = 100) -> List[AgentTrace]:
        """根据用户ID获取轨迹列表"""
        async with async_session() as session:
            result = await session.execute(
                select(AgentTrace)
                .where(AgentTrace.user_id == user_id)
                .order_by(AgentTrace.created_at.desc())
                .limit(limit)
            )
            return list(result.scalars().all())


# 全局存储实例
trace_storage = TraceStorage()
