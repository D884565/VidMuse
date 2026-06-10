"""
通用推送模块
提供WebSocket实时消息推送能力
"""

from .service.push_service import push_service
from .service.connection_manager import connection_manager

__all__ = [
    "push_service",
    "connection_manager"
]

__version__ = "1.0.0"
