"""私有资产存储抽象基类"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

class BaseAssetStore(ABC):
    """
    私有资产存储抽象基类
    每个Agent拥有独立的资产存储空间，用于存储配置、数据、模型、技能等
    """

    @abstractmethod
    def save(self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        保存资产
        :param key: 资产唯一键
        :param value: 资产内容，可以是任意可序列化类型
        :param metadata: 元数据，如创建时间、版本、类型等
        """
        pass

    @abstractmethod
    def load(self, key: str, default: Any = None) -> Any:
        """
        加载资产
        :param key: 资产唯一键
        :param default: 键不存在时返回的默认值
        :return: 资产内容
        """
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """
        删除资产
        :param key: 资产唯一键
        :return: 是否删除成功
        """
        pass

    @abstractmethod
    def exists(self, key: str) -> bool:
        """
        检查资产是否存在
        :param key: 资产唯一键
        :return: 是否存在
        """
        pass

    @abstractmethod
    def list_keys(self, prefix: str = "") -> List[str]:
        """
        列出所有资产键
        :param prefix: 可选前缀，用于过滤
        :return: 资产键列表
        """
        pass

    @abstractmethod
    def get_metadata(self, key: str) -> Optional[Dict[str, Any]]:
        """
        获取资产元数据
        :param key: 资产唯一键
        :return: 元数据，不存在则返回None
        """
        pass
