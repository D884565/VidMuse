"""Lightweight public exports for active search entrypoints."""

from .core.models import Document
from .rag_service_adapter import RAGServiceAdapter
from .rag_trace.dao import AgentTraceDAO, agent_trace_dao
from .rag_trace.dto import (
    AgentTraceBase,
    AgentTraceDetail,
    AgentTraceListResponse,
    TraceQueryRequest,
    TraceStatResponse,
)
from .rag_trace.service import AgentTraceService, agent_trace_service

__version__ = "1.0.0"

__all__ = [
    "Document",
    "RAGServiceAdapter",
    "AgentTraceDAO",
    "agent_trace_dao",
    "AgentTraceBase",
    "AgentTraceDetail",
    "AgentTraceListResponse",
    "TraceQueryRequest",
    "TraceStatResponse",
    "AgentTraceService",
    "agent_trace_service",
]
