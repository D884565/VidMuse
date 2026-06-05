"""BGM 音频库批量导入：扫描本地文件夹，按目录结构生成标签，上传到对象存储。"""
from __future__ import annotations

import os
import uuid
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from backend.store import get_storage_client
from backend.v1.app.assets.dao.asset_dao import AssetDAO
from backend.ffmpeg import ffmpeg_tool

logger = logging.getLogger(__name__)

AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"}

# 目录名 → (维度, 标签值)。未在映射中的目录名默认归入 style。
FOLDER_TAG_MAP: dict[str, tuple[str, str]] = {
    # 情绪
    "轻松": ("emotion", "轻松"),
    "激昂": ("emotion", "激昂"),
    "温暖": ("emotion", "温暖"),
    "紧张": ("emotion", "紧张"),
    "欢快": ("emotion", "欢快"),
    "忧郁": ("emotion", "忧郁"),
    "浪漫": ("emotion", "浪漫"),
    # 场景
    "产品展示": ("scene", "产品展示"),
    "生活日常": ("scene", "生活日常"),
    "科技感": ("scene", "科技感"),
    "美食": ("scene", "美食"),
    "时尚": ("scene", "时尚"),
    "运动": ("scene", "运动"),
    "开箱": ("scene", "开箱"),
    "促销": ("scene", "促销"),
    # 风格
    "电子": ("style", "电子"),
    "钢琴": ("style", "钢琴"),
    "吉他": ("style", "吉他"),
    "管弦": ("style", "管弦"),
    "Lo-fi": ("style", "Lo-fi"),
    "R&B": ("style", "R&B"),
    "嘻哈": ("style", "嘻哈"),
    "轻音乐": ("style", "轻音乐"),
}


def _folder_name_to_tag(folder_name: str) -> tuple[str, str]:
    """将文件夹名映射为 (维度, 标签值)。"""
    if folder_name in FOLDER_TAG_MAP:
        return FOLDER_TAG_MAP[folder_name]
    return ("style", folder_name)


def _get_audio_duration(file_path: str) -> int | None:
    """用 ffprobe 获取音频时长（秒）。"""
    try:
        return int(ffmpeg_tool.get_audio_duration(file_path))
    except Exception:
        return None


def _upload_to_storage(file_path: str, ext: str) -> str:
    """上传文件到对象存储，返回 URL。"""
    client = get_storage_client()
    uuid_str = str(uuid.uuid4()).replace("-", "")
    object_name = f"materials/audio/{uuid_str[:2]}/{uuid_str[2:4]}/{uuid_str}.{ext}"
    return client.upload_file(file_path, object_name)


def import_bgm_folder(db: Session, root_dir: str) -> dict:
    """扫描本地文件夹，将音频文件导入为 BGM 库资产。

    目录结构示例:
        root_dir/
            轻松/
                track1.mp3
                track2.mp3
            电子/
                track3.mp3
            钢琴/
                subfolder/
                    track4.flac   (支持嵌套子目录，父目录标签也保留)

    返回: {"imported": int, "skipped": int, "errors": list[str]}
    """
    root = Path(root_dir)
    if not root.is_dir():
        return {"imported": 0, "skipped": 0, "errors": [f"目录不存在: {root_dir}"]}

    imported = 0
    skipped = 0
    errors = []

    for file_path in sorted(root.rglob("*")):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in AUDIO_EXTENSIONS:
            continue

        try:
            # 从相对路径推断标签
            rel_parts = file_path.relative_to(root).parts
            tags: dict[str, list[str]] = {"emotion": [], "scene": [], "style": []}
            for part in rel_parts[:-1]:  # 排除文件名
                dim, val = _folder_name_to_tag(part)
                if val not in tags[dim]:
                    tags[dim].append(val)

            title = file_path.stem
            ext = file_path.suffix.lower().lstrip(".")
            duration = _get_audio_duration(str(file_path))
            file_size = file_path.stat().st_size

            # 上传到对象存储
            file_url = _upload_to_storage(str(file_path), ext)

            # 创建资产记录
            AssetDAO.create_asset(db, {
                "type": 3,
                "title": title,
                "url": file_url,
                "file_size": file_size,
                "duration": duration,
                "format": ext,
                "tags": tags,
                "scope": "bgm_library",
                "source_type": 2,  # 系统预置
                "user_id": None,
            })
            imported += 1
            logger.info("[BGM导入] %s -> %s", file_path.name, tags)

        except Exception as exc:
            err_msg = f"{file_path}: {exc}"
            errors.append(err_msg)
            logger.warning("[BGM导入失败] %s", err_msg)

    return {"imported": imported, "skipped": skipped, "errors": errors}
