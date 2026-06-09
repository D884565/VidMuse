"""剧本模块

提供剧本生成、版本管理、模板关联、灵感模板查询等功能
"""
__version__ = "1.0.0"

from . import dao
from . import service
from . import controller

__all__ = ["dao", "service", "controller"]

