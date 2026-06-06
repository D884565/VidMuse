"""BGM 音频库批量导入：扫描本地文件夹，按目录结构或文件名生成标签。"""
from __future__ import annotations

import os
import re
import uuid
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from backend.store import get_storage_client
from backend.v1.app.assets.dao.asset_dao import AssetDAO
from backend.ffmpeg import ffmpeg_tool

logger = logging.getLogger(__name__)

AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"}

# 关键词 → (维度, 标签值)。用于从目录名或文件名提取标签。
KEYWORD_TAG_MAP: dict[str, tuple[str, str]] = {
    # 情绪
    "轻松": ("emotion", "轻松"),
    "激昂": ("emotion", "激昂"),
    "温暖": ("emotion", "温暖"),
    "紧张": ("emotion", "紧张"),
    "欢快": ("emotion", "欢快"),
    "忧郁": ("emotion", "忧郁"),
    "浪漫": ("emotion", "浪漫"),
    "感性": ("emotion", "感性"),
    "激情": ("emotion", "激情"),
    "梦幻": ("emotion", "梦幻"),
    "慵懒": ("emotion", "慵懒"),
    "惬意": ("emotion", "惬意"),
    "温柔": ("emotion", "温柔"),
    "活力": ("emotion", "活力"),
    "振奋": ("emotion", "振奋"),
    "励志": ("emotion", "励志"),
    "希望": ("emotion", "希望"),
    "动感": ("emotion", "动感"),
    "伙伴出游": ("emotion", "伙伴出游"),
    # 场景
    "产品展示": ("scene", "产品展示"),
    "产品宣传": ("scene", "产品宣传"),
    "生活日常": ("scene", "生活日常"),
    "科技感": ("scene", "科技感"),
    "科技广告": ("scene", "科技广告"),
    "科技史诗": ("scene", "科技史诗"),
    "元宇宙": ("scene", "元宇宙"),
    "美食": ("scene", "美食"),
    "时尚": ("scene", "时尚"),
    "时尚走秀": ("scene", "时尚走秀"),
    "运动": ("scene", "运动"),
    "开箱": ("scene", "开箱"),
    "促销": ("scene", "促销"),
    "促销活动": ("scene", "促销活动"),
    "电商大促": ("scene", "电商大促"),
    "电商快闪": ("scene", "电商快闪"),
    "海滩日": ("scene", "海滩日"),
    "带货": ("scene", "带货"),
    "快闪": ("scene", "快闪"),
    "MG动画": ("scene", "MG动画"),
    # 风格
    "电子": ("style", "电子"),
    "EDM": ("style", "EDM"),
    "钢琴": ("style", "钢琴"),
    "吉他": ("style", "吉他"),
    "管弦": ("style", "管弦"),
    "Lo-fi": ("style", "Lo-fi"),
    "Lofi": ("style", "Lo-fi"),
    "R&B": ("style", "R&B"),
    "嘻哈": ("style", "嘻哈"),
    "轻音乐": ("style", "轻音乐"),
    "摇滚": ("style", "摇滚"),
    "拉丁节拍": ("style", "拉丁节拍"),
    "舞曲": ("style", "舞曲"),
    "复古": ("style", "复古"),
    "氛围感": ("style", "氛围感"),
    "beat": ("style", "beat"),
    # 补充
    "感性": ("emotion", "感性"),
    "Lofi": ("style", "Lo-fi"),
    "lofi": ("style", "Lo-fi"),
    "辉煌": ("emotion", "辉煌"),
    "清新": ("emotion", "清新"),
    "轻快": ("emotion", "轻快"),
    "懒散": ("emotion", "懒散"),
    "轻柔": ("emotion", "轻柔"),
    "鼓点": ("style", "鼓点"),
    "美妙旅程": ("scene", "美妙旅程"),
    "燃动": ("emotion", "燃动"),
    "迎向新宇宙": ("scene", "迎向新宇宙"),
}


def _keyword_to_tag(keyword: str) -> tuple[str, str] | None:
    """将关键词映射为 (维度, 标签值)，未匹配返回 None。"""
    return KEYWORD_TAG_MAP.get(keyword)


def _extract_tags_from_filename(stem: str) -> dict[str, list[str]]:
    """从文件名提取标签。先按分隔符拆分精确匹配，再用子串匹配补充。"""
    tags: dict[str, list[str]] = {"emotion": [], "scene": [], "style": []}
    # 按分隔符拆分精确匹配
    tokens = re.split(r"[,，_\s]+", stem)
    for token in tokens:
        token = token.strip()
        if not token:
            continue
        mapped = _keyword_to_tag(token)
        if mapped:
            dim, val = mapped
            if val not in tags[dim]:
                tags[dim].append(val)

    # 子串匹配补充（处理连续字符无分隔的情况，如"辉煌活力"）
    sorted_keywords = sorted(KEYWORD_TAG_MAP.keys(), key=len, reverse=True)
    remaining = stem
    for kw in sorted_keywords:
        if kw in remaining:
            dim, val = KEYWORD_TAG_MAP[kw]
            if val not in tags[dim]:
                tags[dim].append(val)
            remaining = remaining.replace(kw, "")

    return tags


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


def _resolve_local_url(file_path: Path, root_dir: str) -> str:
    """生成本地相对路径 URL（相对于项目根目录）。"""
    from backend import PROJECT_ROOT
    try:
        rel = file_path.relative_to(PROJECT_ROOT)
    except ValueError:
        # 如果不在项目根下，用绝对路径
        return str(file_path).replace("\\", "/")
    return str(rel).replace("\\", "/")


def import_bgm_folder(db: Session, root_dir: str, *, local: bool = False) -> dict:
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

    Args:
        local: 为 True 时存本地相对路径（项目自带 BGM），不上传对象存储。

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
                mapped = _keyword_to_tag(part)
                if mapped:
                    dim, val = mapped
                    if val not in tags[dim]:
                        tags[dim].append(val)

            # 如果没有从目录获得标签，从文件名提取
            if not any(tags.values()):
                tags = _extract_tags_from_filename(file_path.stem)

            title = file_path.stem
            ext = file_path.suffix.lower().lstrip(".")
            duration = _get_audio_duration(str(file_path))
            file_size = file_path.stat().st_size

            if local:
                file_url = _resolve_local_url(file_path, root_dir)
            else:
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
