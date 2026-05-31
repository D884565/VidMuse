"""
RAG (Retrieval-Augmented Generation) 模块
提供基于检索的增强生成功能，包括素材管理、向量检索、多模态搜索等
"""



__all__ = ["search"]

from backend.v1.app import search
