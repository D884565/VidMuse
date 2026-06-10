"""FFmpeg 工具类 — 兼容层。

所有实际功能已统一到 backend.ffmpeg.pyutils.FFmpegVideoTool。
本模块仅保留导入路径兼容，避免大规模改动调用方。
"""
from backend.ffmpeg.pyutils import (
    FFmpegVideoTool,
    ffmpeg_tool,
    FFMPEG_PATH,
    FFPROBE_PATH,
)

# 兼容旧接口：ffmpeg_utils.XXX()
FFmpegUtils = FFmpegVideoTool
ffmpeg_utils = ffmpeg_tool

__all__ = [
    "FFmpegUtils",
    "ffmpeg_utils",
    "FFmpegVideoTool",
    "ffmpeg_tool",
    "FFMPEG_PATH",
    "FFPROBE_PATH",
]
