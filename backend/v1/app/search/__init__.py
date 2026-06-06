"""Lightweight public exports for active search entrypoints."""

from .core.models import Document
from .rag_service_adapter import RAGServiceAdapter

__version__ = "1.0.0"

__all__ = [
    "Document",
    "RAGServiceAdapter",
]
