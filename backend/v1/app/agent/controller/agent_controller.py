from fastapi import APIRouter, Path, Body
from backend.framework.web.response import Response
from ..dto.request import CreateSessionRequest, ChatRequest
from ..dto.response import CreateSessionResponse, ChatResponse, SessionHistoryResponse
from ..service import agent_service

router = APIRouter(prefix="/agent", tags=["智能Agent"])


@router.post("/session", response_model=Response[CreateSessionResponse], summary="创建新会话")
def create_session(
        request: CreateSessionRequest = Body(..., description="创建会话请求")
):
    """创建新的对话会话，返回session_id用于后续对话"""
    result = agent_service.create_session(request)
    return Response.success(data=result, message="会话创建成功")


@router.post("/chat", response_model=Response[ChatResponse], summary="发送消息进行聊天")
def chat(
        request: ChatRequest = Body(..., description="聊天请求")
):
    """发送用户消息，获取Agent回答，支持工具调用"""
    result = agent_service.send_message(request)
    return Response.success(data=result, message="请求成功")


@router.get("/session/{session_id}/history", response_model=Response[SessionHistoryResponse], summary="获取会话历史")
def get_session_history(
        session_id: str = Path(..., description="会话ID")
):
    """获取指定会话的消息历史"""
    result = agent_service.get_session_history(session_id)
    if not result:
        return Response.fail(message="会话不存在或已过期")
    return Response.success(data=result, message="获取成功")


@router.delete("/session/{session_id}", response_model=Response, summary="删除会话")
def delete_session(
        session_id: str = Path(..., description="会话ID")
):
    """删除指定会话，释放资源"""
    success = agent_service.delete_session(session_id)
    if success:
        return Response.success(message="会话删除成功")
    return Response.fail(message="会话不存在或删除失败")
