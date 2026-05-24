from pathlib import Path

try:
    from .keyframes import (
        ExtractedFrame,
        VideoKeyframeResult,
        extract_keyframes_by_interval,
        extract_keyframes_for_videos,
        get_keyframe_paths_by_video,
        get_keyframe_records_by_video,
    )
except ImportError:
    from keyframes import (
        ExtractedFrame,
        VideoKeyframeResult,
        extract_keyframes_by_interval,
        extract_keyframes_for_videos,
        get_keyframe_paths_by_video,
        get_keyframe_records_by_video,
    )


def demo_extract_keyframes() -> VideoKeyframeResult:
    """Small local demo for fixed-interval keyframe extraction."""
    project_root = Path(__file__).resolve().parents[4]
    results = extract_keyframes_for_videos(
        video_paths=[project_root / "backend" / "opencv_demo" / "ee314fff8bbd23bf549d2f4a018e54cf.mp4"],
        output_root=project_root / "backend" / "v1" / "app" / "cvcode" / "demo_keyframes",
        interval_seconds=2,
    )
    return results[0]


__all__ = [
    "ExtractedFrame",
    "VideoKeyframeResult",
    "demo_extract_keyframes",
    "extract_keyframes_by_interval",
    "extract_keyframes_for_videos",
    "get_keyframe_paths_by_video",
    "get_keyframe_records_by_video",
]


if __name__ == "__main__":
    result = demo_extract_keyframes()
    print(f"video_id: {result.video_id}")
    print(f"video_name: {result.video_name}")
    print(f"opened: {result.opened}")
    print(f"saved_count: {result.saved_count}")
    for frame in result.keyframes:
        print(f"{frame.video_id} | {frame.timestamp_text} | {frame.image_path}")

    print("\nquery saved keyframe paths:")
    paths_by_video = get_keyframe_paths_by_video(
        video_paths=result.video_path,
        output_root=Path(result.output_dir).parent,
    )
    for video_id, paths in paths_by_video.items():
        print(f"{video_id}: {len(paths)} path(s)")
        for path in paths:
            print(path)
