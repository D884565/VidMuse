from typing import Any, Dict, List, Optional


class PipelineContext:
    """流水线上下文，用于在处理器之间传递数据和状态"""

    def __init__(self, initial_data: Optional[Dict[str, Any]] = None):
        self.data: Dict[str, Any] = initial_data or {}  # 业务数据存储
        self.errors: List[Exception] = []  # 错误信息存储
        self.metadata: Dict[str, Any] = {}  # 元数据/临时存储

    def get(self, key: str, default: Any = None) -> Any:
        """
        从上下文中获取数据

        :param key: 数据键名
        :param default: 默认值（当键不存在时返回）
        :return: 数据值
        """
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        设置上下文数据

        :param key: 数据键名
        :param value: 数据值
        """
        self.data[key] = value

    def add_error(self, error: Exception) -> None:
        """
        添加错误信息

        :param error: 异常对象
        """
        self.errors.append(error)

    def has_errors(self) -> bool:
        """
        检查上下文中是否有错误

        :return: 有错误返回True，否则返回False
        """
        return len(self.errors) > 0

    def get_errors(self) -> List[str]:
        """
        获取所有错误信息的字符串表示

        :return: 错误信息列表
        """
        return [str(e) for e in self.errors]
