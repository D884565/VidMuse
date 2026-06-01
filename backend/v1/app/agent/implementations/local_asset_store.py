"""本地资产存储实现"""
import os
import json
from typing import Any, Dict, List, Optional
from datetime import datetime
from ..core.asset import BaseAssetStore
from ..config import AGENT_CONFIG

class LocalAssetStore(BaseAssetStore):
    """
    本地文件系统资产存储实现
    每个Agent的资产存储在独立的目录下，使用JSON格式序列化
    """

    def __init__(self, agent_id: str, base_path: Optional[str] = None):
        """
        初始化本地资产存储
        :param agent_id: Agent唯一标识，用于创建独立的存储目录
        :param base_path: 资产存储根路径，默认使用配置中的值
        """
        self.agent_id = agent_id
        self.base_path = base_path or AGENT_CONFIG["asset"]["base_storage_path"]
        self.agent_dir = os.path.join(self.base_path, agent_id)

        # 确保Agent目录存在
        os.makedirs(self.agent_dir, exist_ok=True)
        self._meta_file = os.path.join(self.agent_dir, ".metadata.json")
        self._metadata = self._load_metadata()

    def _load_metadata(self) -> Dict[str, Dict[str, Any]]:
        """加载资产元数据"""
        if os.path.exists(self._meta_file):
            with open(self._meta_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save_metadata(self) -> None:
        """保存资产元数据"""
        with open(self._meta_file, "w", encoding="utf-8") as f:
            json.dump(self._metadata, f, ensure_ascii=False, indent=2)

    def _get_asset_path(self, key: str) -> str:
        """获取资产文件路径"""
        # 将key中的/转换为目录分隔符
        relative_path = key.replace("/", os.sep) + ".json"
        return os.path.join(self.agent_dir, relative_path)

    def save(self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None) -> None:
        asset_path = self._get_asset_path(key)

        # 确保目录存在
        os.makedirs(os.path.dirname(asset_path), exist_ok=True)

        # 保存资产内容
        with open(asset_path, "w", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=False, indent=2)

        # 更新元数据
        self._metadata[key] = {
            "key": key,
            "file_path": asset_path,
            "size": os.path.getsize(asset_path),
            "created_at": self._metadata.get(key, {}).get("created_at", datetime.now().isoformat()),
            "updated_at": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        self._save_metadata()

    def load(self, key: str, default: Any = None) -> Any:
        if not self.exists(key):
            return default

        asset_path = self._get_asset_path(key)
        try:
            with open(asset_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            return default

    def delete(self, key: str) -> bool:
        if not self.exists(key):
            return False

        asset_path = self._get_asset_path(key)
        try:
            os.remove(asset_path)
            del self._metadata[key]
            self._save_metadata()

            # 清理空目录
            dir_path = os.path.dirname(asset_path)
            if dir_path.startswith(self.agent_dir) and os.path.isdir(dir_path):
                if not os.listdir(dir_path):
                    os.rmdir(dir_path)

            return True
        except Exception as e:
            return False

    def exists(self, key: str) -> bool:
        return key in self._metadata and os.path.exists(self._get_asset_path(key))

    def list_keys(self, prefix: str = "") -> List[str]:
        if not prefix:
            return list(self._metadata.keys())

        return [key for key in self._metadata.keys() if key.startswith(prefix)]

    def get_metadata(self, key: str) -> Optional[Dict[str, Any]]:
        if key not in self._metadata:
            return None

        return self._metadata[key]["metadata"].copy()
