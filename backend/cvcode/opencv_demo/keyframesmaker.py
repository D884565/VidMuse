import os
import re
import uuid
import tempfile
from urllib.parse import quote
from typing import Any

import cv2
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel


app = FastAPI(title="OpenCV Video Keyframe Test")
DEFAULT_KEYFRAME_DIR = "backend/opencv/keyframes"
STATIC_KEYFRAME_ROUTE = "/keyframes-static"
os.makedirs(DEFAULT_KEYFRAME_DIR, exist_ok=True)
app.mount(STATIC_KEYFRAME_ROUTE, StaticFiles(directory=DEFAULT_KEYFRAME_DIR), name="keyframes")


class VideoReadResult(BaseModel):
    filename: str
    opencv_version: str
    opened: bool
    frame_count: int
    fps: float
    width: int
    height: int
    duration_seconds: float
    sampled_frames: int
    first_frame_read: bool
    message: str


class SavedKeyframe(BaseModel):
    frame_index: int
    timestamp_seconds: float
    change_score: float
    path: str
    url: str


class KeyframeChangeResult(BaseModel):
    filename: str
    opencv_version: str
    opened: bool
    frame_count: int
    fps: float
    width: int
    height: int
    change_threshold: float
    min_interval_seconds: float
    resize_width: int
    max_keyframes: int
    saved_count: int
    output_dir: str
    keyframes: list[SavedKeyframe]
    message: str


def _round_float(value: Any, digits: int = 3) -> float:
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return 0.0


def _parse_float(value: str | None, default: float, minimum: float) -> float:
    if value in (None, ""):
        return default
    try:
        parsed = float(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid float value: {value}") from exc
    if parsed < minimum:
        raise HTTPException(status_code=400, detail=f"Value must be >= {minimum}: {value}")
    return parsed


def _parse_int(value: str | None, default: int, minimum: int, maximum: int) -> int:
    if value in (None, ""):
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid integer value: {value}") from exc
    if parsed < minimum or parsed > maximum:
        raise HTTPException(status_code=400, detail=f"Value must be between {minimum} and {maximum}: {value}")
    return parsed


def _get_upload(file: UploadFile | None, video: UploadFile | None) -> UploadFile:
    upload = file or video
    if upload is None:
        raise HTTPException(
            status_code=400,
            detail="Upload a video file using multipart/form-data field 'file' or 'video'.",
        )
    return upload


async def _save_upload_to_temp(upload: UploadFile) -> str:
    suffix = os.path.splitext(upload.filename or "")[1] or ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_path = temp_file.name
        while chunk := await upload.read(1024 * 1024):
            temp_file.write(chunk)
    return temp_path


def _keyframe_url(path: str, output_dir: str) -> str:
    if os.path.normpath(output_dir) != os.path.normpath(DEFAULT_KEYFRAME_DIR):
        return ""
    return f"{STATIC_KEYFRAME_ROUTE}/{quote(os.path.basename(path))}"


def _safe_video_stem(filename: str | None) -> str:
    stem = os.path.splitext(os.path.basename(filename or "video"))[0]
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", stem).strip("._-")
    if safe:
        return safe[:48]
    return uuid.uuid4().hex


def _write_jpeg(path: str, frame) -> None:
    ok, encoded = cv2.imencode(".jpg", frame)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to encode keyframe as JPEG.")
    encoded.tofile(path)


@app.get("/", response_class=HTMLResponse)
async def home():
    return """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>OpenCV Keyframe Viewer</title>
  <style>
    :root { font-family: Arial, sans-serif; color: #172033; background: #f4f6fa; }
    body { margin: 0; }
    main { max-width: 1180px; margin: 0 auto; padding: 28px; }
    h1 { font-size: 24px; margin: 0 0 18px; }
    form { display: grid; grid-template-columns: repeat(5, minmax(120px, 1fr)); gap: 12px; align-items: end; background: #fff; border: 1px solid #dfe5ee; padding: 16px; border-radius: 8px; }
    label { display: grid; gap: 6px; font-size: 13px; color: #536173; }
    input { box-sizing: border-box; width: 100%; height: 36px; border: 1px solid #c9d3e0; border-radius: 6px; padding: 0 10px; background: #fff; }
    input[type="file"] { padding: 7px 8px; }
    button { height: 36px; border: 0; border-radius: 6px; background: #1864ab; color: #fff; font-weight: 700; cursor: pointer; }
    button:disabled { background: #8aa8c6; cursor: wait; }
    .status { margin: 16px 0; font-size: 14px; color: #536173; min-height: 20px; }
    .summary { display: grid; grid-template-columns: repeat(6, minmax(120px, 1fr)); gap: 10px; margin-bottom: 16px; }
    .metric { background: #fff; border: 1px solid #dfe5ee; border-radius: 8px; padding: 12px; }
    .metric span { display: block; font-size: 12px; color: #69788a; }
    .metric strong { display: block; margin-top: 6px; font-size: 18px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 14px; }
    .card { background: #fff; border: 1px solid #dfe5ee; border-radius: 8px; overflow: hidden; }
    .card img { width: 100%; aspect-ratio: 16 / 9; object-fit: cover; display: block; background: #dde5ef; }
    .meta { padding: 10px 12px; display: grid; gap: 4px; font-size: 13px; color: #536173; overflow-wrap: anywhere; }
    .meta strong { color: #172033; }
    @media (max-width: 820px) { form, .summary { grid-template-columns: 1fr 1fr; } main { padding: 16px; } }
  </style>
</head>
<body>
  <main>
    <h1>OpenCV Keyframe Viewer</h1>
    <form id="form">
      <label>Video file<input name="file" type="file" accept="video/*" required /></label>
      <label>Change threshold<input name="change_threshold" type="number" step="0.5" min="0" value="18" /></label>
      <label>Min interval sec<input name="min_interval_seconds" type="number" step="0.1" min="0" value="1" /></label>
      <label>Detect width<input name="resize_width" type="number" min="32" max="1920" value="320" /></label>
      <label>Max keyframes<input name="max_keyframes" type="number" min="1" max="500" value="20" /></label>
      <button id="submit" type="submit">Detect</button>
    </form>
    <div id="status" class="status"></div>
    <section id="summary" class="summary"></section>
    <section id="grid" class="grid"></section>
  </main>
  <script>
    const form = document.querySelector("#form");
    const statusEl = document.querySelector("#status");
    const summaryEl = document.querySelector("#summary");
    const gridEl = document.querySelector("#grid");
    const button = document.querySelector("#submit");

    function metric(label, value) {
      return `<div class="metric"><span>${label}</span><strong>${value}</strong></div>`;
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      button.disabled = true;
      statusEl.textContent = "Uploading and analyzing video...";
      summaryEl.innerHTML = "";
      gridEl.innerHTML = "";

      try {
        const body = new FormData(form);
        const response = await fetch("/video/keyframes/change-detect", { method: "POST", body });
        if (!response.ok) {
          throw new Error(await response.text());
        }

        const data = await response.json();
        statusEl.textContent = data.message;
        summaryEl.innerHTML = [
          metric("Saved", data.saved_count),
          metric("Frames", data.frame_count),
          metric("FPS", data.fps),
          metric("Size", `${data.width}x${data.height}`),
          metric("Threshold", data.change_threshold),
          metric("Interval", `${data.min_interval_seconds}s`)
        ].join("");

        if (!data.keyframes.length) {
          gridEl.innerHTML = "<p>No keyframes were saved. Try a lower threshold such as 6 or 10.</p>";
          return;
        }

        gridEl.innerHTML = data.keyframes.map((item) => `
          <article class="card">
            <img src="${item.url}?t=${Date.now()}" alt="frame ${item.frame_index}" />
            <div class="meta">
              <strong>Frame ${item.frame_index}</strong>
              <span>Time: ${item.timestamp_seconds}s</span>
              <span>Change score: ${item.change_score}</span>
              <span>${item.path}</span>
            </div>
          </article>
        `).join("");
      } catch (error) {
        statusEl.textContent = `Failed: ${error.message}`;
      } finally {
        button.disabled = false;
      }
    });
  </script>
</body>
</html>
"""


@app.post("/video/read-test", response_model=VideoReadResult)
async def read_video_test(
    file: UploadFile | None = File(default=None),
    video: UploadFile | None = File(default=None),
):
    upload = _get_upload(file, video)
    temp_path = ""
    cap = None

    try:
        temp_path = await _save_upload_to_temp(upload)
        cap = cv2.VideoCapture(temp_path)
        opened = cap.isOpened()

        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) if opened else 0
        fps = _round_float(cap.get(cv2.CAP_PROP_FPS)) if opened else 0.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) if opened else 0
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) if opened else 0
        duration = _round_float(frame_count / fps) if fps > 0 else 0.0

        first_frame_read = False
        sampled_frames = 0
        if opened:
            for _ in range(10):
                ok, _frame = cap.read()
                if not ok:
                    break
                sampled_frames += 1
                first_frame_read = True

        message = "Video opened and frames were read." if first_frame_read else "Video could not be read."
        return VideoReadResult(
            filename=upload.filename or "",
            opencv_version=cv2.__version__,
            opened=opened,
            frame_count=frame_count,
            fps=fps,
            width=width,
            height=height,
            duration_seconds=duration,
            sampled_frames=sampled_frames,
            first_frame_read=first_frame_read,
            message=message,
        )
    finally:
        if cap is not None:
            cap.release()
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@app.post("/video/keyframes/change-detect", response_model=KeyframeChangeResult)
async def save_keyframes_on_change(
    file: UploadFile | None = File(default=None),
    video: UploadFile | None = File(default=None),
    change_threshold: str = Form(default="18"),
    min_interval_seconds: str = Form(default="1"),
    resize_width: str = Form(default="320"),
    max_keyframes: str = Form(default="20"),
    output_dir: str = Form(default=DEFAULT_KEYFRAME_DIR),
):
    upload = _get_upload(file, video)
    change_threshold_value = _parse_float(change_threshold, default=18.0, minimum=0.0)
    min_interval_seconds_value = _parse_float(min_interval_seconds, default=1.0, minimum=0.0)
    resize_width_value = _parse_int(resize_width, default=320, minimum=32, maximum=1920)
    max_keyframes_value = _parse_int(max_keyframes, default=20, minimum=1, maximum=500)

    temp_path = ""
    cap = None
    keyframes: list[SavedKeyframe] = []

    try:
        temp_path = await _save_upload_to_temp(upload)
        os.makedirs(output_dir, exist_ok=True)

        cap = cv2.VideoCapture(temp_path)
        opened = cap.isOpened()
        if not opened:
            return KeyframeChangeResult(
                filename=upload.filename or "",
                opencv_version=cv2.__version__,
                opened=False,
                frame_count=0,
                fps=0.0,
                width=0,
                height=0,
                change_threshold=change_threshold_value,
                min_interval_seconds=min_interval_seconds_value,
                resize_width=resize_width_value,
                max_keyframes=max_keyframes_value,
                saved_count=0,
                output_dir=output_dir,
                keyframes=[],
                message="Video could not be opened.",
            )

        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = _round_float(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        min_interval_frames = int(fps * min_interval_seconds_value) if fps > 0 else 0

        reference_gray = None
        last_saved_frame = -min_interval_frames
        frame_index = -1
        basename = _safe_video_stem(upload.filename)

        while len(keyframes) < max_keyframes_value:
            ok, frame = cap.read()
            if not ok:
                break

            frame_index += 1
            scale = resize_width_value / frame.shape[1]
            resized = cv2.resize(frame, (resize_width_value, max(1, int(frame.shape[0] * scale))))
            gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (5, 5), 0)

            if reference_gray is None:
                reference_gray = gray
                continue

            diff = cv2.absdiff(reference_gray, gray)
            change_score = _round_float(diff.mean())
            enough_interval = frame_index - last_saved_frame >= min_interval_frames

            if change_score >= change_threshold_value and enough_interval:
                timestamp = _round_float(frame_index / fps) if fps > 0 else 0.0
                filename = f"{basename}_frame_{frame_index:06d}_score_{change_score:.2f}.jpg"
                save_path = os.path.join(output_dir, filename)
                _write_jpeg(save_path, frame)

                keyframes.append(
                    SavedKeyframe(
                        frame_index=frame_index,
                        timestamp_seconds=timestamp,
                        change_score=change_score,
                        path=save_path,
                        url=_keyframe_url(save_path, output_dir),
                    )
                )
                last_saved_frame = frame_index
                reference_gray = gray

        return KeyframeChangeResult(
            filename=upload.filename or "",
            opencv_version=cv2.__version__,
            opened=True,
            frame_count=frame_count,
            fps=fps,
            width=width,
            height=height,
            change_threshold=change_threshold_value,
            min_interval_seconds=min_interval_seconds_value,
            resize_width=resize_width_value,
            max_keyframes=max_keyframes_value,
            saved_count=len(keyframes),
            output_dir=output_dir,
            keyframes=keyframes,
            message=f"Saved {len(keyframes)} keyframe(s).",
        )
    finally:
        if cap is not None:
            cap.release()
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
