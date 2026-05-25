import hashlib
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import cv2


@dataclass(slots=True)
class ExtractedFrame:
    video_id: str
    video_name: str
    frame_index: int
    timestamp_seconds: float
    timestamp_text: str
    image_path: str

    @property
    def path(self) -> str:
        return self.image_path


@dataclass(slots=True)
class VideoKeyframeResult:
    video_id: str
    video_name: str
    video_path: str
    output_dir: str
    opened: bool
    frame_count: int = 0
    fps: float = 0.0
    width: int = 0
    height: int = 0
    interval_seconds: float = 0.0
    keyframes: list[ExtractedFrame] = field(default_factory=list)
    message: str = ""

    @property
    def saved_count(self) -> int:
        return len(self.keyframes)


def extract_keyframes_by_interval(
    video_path: str | os.PathLike[str],
    output_dir: str | os.PathLike[str],
    interval_seconds: float,
) -> VideoKeyframeResult:
    """Extract frames from one video at a fixed time interval.

    The extraction continues until the video ends. No gray-scale/change detection
    is used, so the maximum saved frame count is decided only by video duration.
    """
    video_path = str(video_path)
    output_dir = str(output_dir)
    _validate_interval(interval_seconds)

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    video_id = _video_id(video_path)
    video_name = Path(video_path).name
    try:
        if not cap.isOpened():
            return VideoKeyframeResult(
                video_id=video_id,
                video_name=video_name,
                video_path=video_path,
                output_dir=output_dir,
                opened=False,
                interval_seconds=interval_seconds,
                message="Video could not be opened.",
            )

        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = _round_float(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        if fps <= 0:
            return VideoKeyframeResult(
                video_id=video_id,
                video_name=video_name,
                video_path=video_path,
                output_dir=output_dir,
                opened=True,
                frame_count=frame_count,
                fps=fps,
                width=width,
                height=height,
                interval_seconds=interval_seconds,
                message="Video FPS is invalid, so fixed-interval extraction cannot run.",
            )

        interval_frames = max(1, round(fps * interval_seconds))
        saved_frames: list[ExtractedFrame] = []
        basename = video_id

        target_frame_index = 0
        while frame_count <= 0 or target_frame_index < frame_count:
            cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame_index)
            ok, frame = cap.read()
            if not ok:
                break

            timestamp = _round_float(target_frame_index / fps)
            timestamp_text = _format_timestamp(timestamp)
            filename = f"{basename}_frame_{target_frame_index:06d}_{timestamp:.3f}s.jpg"
            save_path = os.path.join(output_dir, filename)
            _write_jpeg(save_path, frame)

            saved_frames.append(
                ExtractedFrame(
                    video_id=video_id,
                    video_name=video_name,
                    frame_index=target_frame_index,
                    timestamp_seconds=timestamp,
                    timestamp_text=timestamp_text,
                    image_path=save_path,
                )
            )
            target_frame_index += interval_frames

        return VideoKeyframeResult(
            video_id=video_id,
            video_name=video_name,
            video_path=video_path,
            output_dir=output_dir,
            opened=True,
            frame_count=frame_count,
            fps=fps,
            width=width,
            height=height,
            interval_seconds=interval_seconds,
            keyframes=saved_frames,
            message=f"Saved {len(saved_frames)} keyframe(s).",
        )
    finally:
        cap.release()


def extract_keyframes_for_videos(
    video_paths: Iterable[str | os.PathLike[str]],
    output_root: str | os.PathLike[str],
    interval_seconds: float,
) -> list[VideoKeyframeResult]:
    """Extract fixed-interval keyframes for many videos.

    Each video gets its own subfolder under output_root.
    """
    _validate_interval(interval_seconds)
    results: list[VideoKeyframeResult] = []

    for video_path in video_paths:
        video_path = str(video_path)
        video_output_dir = Path(output_root) / _video_id(video_path)
        results.append(
            extract_keyframes_by_interval(
                video_path=video_path,
                output_dir=video_output_dir,
                interval_seconds=interval_seconds,
            )
        )

    return results


def get_keyframe_paths_by_video(
    video_paths: str | os.PathLike[str] | Iterable[str | os.PathLike[str]],
    output_root: str | os.PathLike[str],
) -> dict[str, list[str]]:
    """Query saved keyframe image paths grouped by video id.

    This function does not extract frames. It only reads keyframe files that were
    already saved by extract_keyframes_by_interval or extract_keyframes_for_videos.
    """
    paths = _normalize_video_paths(video_paths)
    return {video_id: _list_saved_keyframe_paths(output_root, video_id) for video_id in map(_video_id, paths)}


def get_keyframe_records_by_video(
    video_paths: str | os.PathLike[str] | Iterable[str | os.PathLike[str]],
    output_root: str | os.PathLike[str],
) -> dict[str, list[ExtractedFrame]]:
    """Query saved keyframe objects grouped by video id."""
    paths = _normalize_video_paths(video_paths)
    records: dict[str, list[ExtractedFrame]] = {}

    for video_path in paths:
        video_path = str(video_path)
        video_id = _video_id(video_path)
        video_name = Path(video_path).name
        records[video_id] = [
            _frame_from_saved_path(path, video_id, video_name)
            for path in _list_saved_keyframe_paths(output_root, video_id)
        ]

    return records


def _normalize_video_paths(
    video_paths: str | os.PathLike[str] | Iterable[str | os.PathLike[str]],
) -> list[str | os.PathLike[str]]:
    if isinstance(video_paths, (str, os.PathLike)):
        return [video_paths]
    return list(video_paths)


def _list_saved_keyframe_paths(output_root: str | os.PathLike[str], video_id: str) -> list[str]:
    video_dir = Path(output_root) / video_id
    if not video_dir.exists() or not video_dir.is_dir():
        return []
    return [str(path) for path in sorted(video_dir.glob("*.jpg"), key=_keyframe_sort_key)]


def _keyframe_sort_key(path: Path) -> tuple[int, str]:
    match = re.search(r"_frame_(\d+)_", path.name)
    if match:
        return int(match.group(1)), path.name
    return 0, path.name


def _frame_from_saved_path(path: str, video_id: str, video_name: str) -> ExtractedFrame:
    frame_index = 0
    timestamp_seconds = 0.0

    match = re.search(r"_frame_(\d+)_([0-9.]+)s\.jpg$", Path(path).name)
    if match:
        frame_index = int(match.group(1))
        timestamp_seconds = _round_float(float(match.group(2)))

    return ExtractedFrame(
        video_id=video_id,
        video_name=video_name,
        frame_index=frame_index,
        timestamp_seconds=timestamp_seconds,
        timestamp_text=_format_timestamp(timestamp_seconds),
        image_path=path,
    )


def _validate_interval(interval_seconds: float) -> None:
    if interval_seconds <= 0:
        raise ValueError("interval_seconds must be greater than 0.")


def _round_float(value: float, digits: int = 3) -> float:
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return 0.0


def _safe_video_stem(video_path: str) -> str:
    stem = Path(video_path).stem or "video"
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", stem).strip("._-")
    return safe[:48] if safe else "video"


def _video_id(video_path: str) -> str:
    safe_stem = _safe_video_stem(video_path)
    resolved_path = str(Path(video_path).resolve()).encode("utf-8")
    path_hash = hashlib.md5(resolved_path, usedforsecurity=False).hexdigest()[:8]
    return f"{safe_stem}_{path_hash}"


def _format_timestamp(timestamp_seconds: float) -> str:
    total_milliseconds = int(round(timestamp_seconds * 1000))
    milliseconds = total_milliseconds % 1000
    total_seconds = total_milliseconds // 1000
    seconds = total_seconds % 60
    total_minutes = total_seconds // 60
    minutes = total_minutes % 60
    hours = total_minutes // 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"


def _write_jpeg(path: str, frame) -> None:
    ok, encoded = cv2.imencode(".jpg", frame)
    if not ok:
        raise RuntimeError("Failed to encode keyframe as JPEG.")
    encoded.tofile(path)
