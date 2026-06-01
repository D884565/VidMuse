"""资产序列化工具"""
import json
import pickle
from typing import Any
from enum import Enum

class SerializerType(Enum):
    """序列化类型"""
    JSON = "json"
    PICKLE = "pickle"

class AssetSerializer:
    """资产序列化工具，支持多种序列化格式"""

    @staticmethod
    def serialize(obj: Any, serializer_type: SerializerType = SerializerType.JSON) -> bytes:
        """序列化对象"""
        if serializer_type == SerializerType.JSON:
            return json.dumps(obj, ensure_ascii=False).encode("utf-8")
        elif serializer_type == SerializerType.PICKLE:
            return pickle.dumps(obj)
        else:
            raise ValueError(f"不支持的序列化类型: {serializer_type}")

    @staticmethod
    def deserialize(data: bytes, serializer_type: SerializerType = SerializerType.JSON) -> Any:
        """反序列化对象"""
        if serializer_type == SerializerType.JSON:
            return json.loads(data.decode("utf-8"))
        elif serializer_type == SerializerType.PICKLE:
            return pickle.loads(data)
        else:
            raise ValueError(f"不支持的序列化类型: {serializer_type}")
