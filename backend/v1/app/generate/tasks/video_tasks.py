"""基于分镜帧的 Celery 视频生成任务。"""
import os
import logging
import tempfile
import shutil
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.v1.app.generate.tasks.celery_app import celery_app
from backend.store.database.sync_database import SessionLocal
from backend.v1.app.models.project import Project
from backend.v1.app.models.frame import Frame
from backend.providers.tts import tts_service
from backend.v1.app.generate.service.generateUtils.external_call_policy import ALLOW_DEGRADED_AUDIO
from backend.v1.app.generate.service.stages.image_service import image_generation_service
from backend.v1.app.generate.service.generateUtils.reference_image_utils import extract_reference_images
from backend.v1.app.generate.service.stages.video_composer import video_composer
from backend.v1.app.generate.service.workflow.media_resolvers import resolve_tts_text
from backend.ffmpeg import ffmpeg_tool
from backend.v1.app.generate.service.stages.bgm_selector import bgm_selector_service
from backend.v1.app.generate.service.generateUtils.task_service import generation_task_service
from backend.v1.app.generate.service.generateUtils.task_tracker import generation_task_tracker
from backend.v1.app.generate.service.generateUtils.retry_coordinator import retry_coordinator
from backend.v1.app.models.script import Script
from backend.v1.app.assets.dao.asset_dao import AssetDAO
from backend.v1.app.generate.service.workflow.blocks import build_video_stage_blocks
from backend.v1.app.generate.service.stages.image_workflow import build_image_stage_message
from backend.v1.app.generate.service.workflow import state as project_workflow_state
from backend.v1.app.models.conversation import Conversation
from backend.store.obj.factory import get_storage_client

logger = logging.getLogger(__name__)

MAX_TTS_OVERRUN_SECONDS = float(os.getenv("MAX_TTS_OVERRUN_SECONDS", "0.5"))
TAIL_PADDING_SECONDS = float(os.getenv("TTS_TAIL_PADDING_SECONDS", "0.25"))


class GenerationStageError(RuntimeError):
    """携带失败阶段信息，交给统一失败处理器决定是否最终落库。"""

    def __init__(self, *, stage: str, current_step: str, error_code: str, message: str):
        super().__init__(message)
        self.stage = stage
        self.current_step = current_step
        self.error_code = error_code


# Celery Worker 使用同步数据库连接
def _get_sync_db() -> Session:
    return SessionLocal()


def _retry_countdown(retries: int) -> int:
    return min(300, 2 ** max(0, retries))


def ensure_task_not_cancelled(db: Session, task_id: int | None) -> None:
    if not task_id:
        return
    task = generation_task_service.get_task_sync(db, task_id)
    if task.status == "cancelled":
        raise ValueError(f"generation task cancelled: {task_id}")


def _persist_frame_video_segment(project_id: int, frame: Frame, local_path: str) -> str:
    object_key = f"projects/{project_id}/frames/frame_{frame.id or frame.sequence}.mp4"
    video_url = get_storage_client().upload_file(local_path, object_key)
    return video_url


def _resolve_frame_narration_text(frame: Frame) -> str:
    return resolve_tts_text(frame)


def _resolve_frame_voice_type(project: Project, frame: Frame) -> str:
    voice_map = {
        "excited": "zh_female_cancan_mars_bigtts",
        "confident": "zh_female_shuangkuai_moon_bigtts",
        "urgent": "zh_male_chunhou_mars_bigtts",
        "warm": "zh_female_tianmei_mars_bigtts",
        "professional": "zh_male_yangguang_mars_bigtts",
    }
    if getattr(project, "voice_type", None):
        return project.voice_type
    frame_style = (frame.ai_params or {}).get("voice_style", "")
    return voice_map.get(frame_style, "zh_female_cancan_mars_bigtts")


def _frame_needs_video_generation(frame: Frame) -> bool:
    video_url = getattr(frame, "video_url", None)
    return not video_url or not str(video_url).startswith("http") or bool(getattr(frame, "dirty", 0))


def _reload_project_frames(db: Session, project_id: int) -> list[Frame]:
    db.expire_all()
    return list(db.execute(
        select(Frame)
        .where(Frame.project_id == project_id)
        .order_by(Frame.sequence)
    ).scalars())


def _compose_frame_video_urls(frames: list[Frame], output_dir: str, target_duration: float | None = None) -> str:
    os.makedirs(output_dir, exist_ok=True)
    video_composer.validate_frames_for_video(frames)

    video_paths = []
    for frame in frames:
        video_url = getattr(frame, "video_url", None)
        if not video_url or not str(video_url).startswith("http"):
            raise GenerationStageError(
                stage="video",
                current_step="VIDEO_SEGMENT_GENERATION_FAILED",
                error_code="VIDEO_SEGMENT_GENERATION_FAILED",
                message=f"frame {frame.id} missing generated video_url",
            )
        local_path = os.path.join(output_dir, f"frame_{frame.sequence}_{frame.id}_segment.mp4")
        video_composer._download_video(video_url, local_path)
        video_composer._validate_local_video(local_path)
        video_paths.append(local_path)

    if len(video_paths) > 1:
        final_path = video_composer._concat_videos(video_paths, output_dir)
    elif video_paths:
        final_path = video_paths[0]
    else:
        final_path = video_composer._generate_placeholder_video(output_dir, 30, 0)

    if target_duration:
        return video_composer._trim_final_video(final_path, output_dir, target_duration)
    return final_path


def _write_frame_image_regeneration_conversation(
    db: Session,
    project: Project,
    frame: Frame,
    task_id: int | None,
) -> None:
    frames = list(db.execute(
        select(Frame)
        .where(Frame.project_id == project.id)
        .order_by(Frame.sequence)
    ).scalars())
    all_images_ready = bool(frames) and all(getattr(item, "image_url", None) for item in frames)
    original_stage = getattr(project, "workflow_stage", None)
    if original_stage in ("video", "completed"):
        project_workflow_state.invalidate_project_from(project, "video")
    elif all_images_ready:
        project_workflow_state.mark_project_stage_review(project, "image", task_id)

    db.add(Conversation(
        project_id=project.id,
        role="assistant",
        content=f"第{frame.sequence}个分镜的图片已重新生成。"
        + ("你可以确认图片并继续生成视频。" if all_images_ready else ""),
        message_type="stage_card",
        stage="image",
        blocks=[
            {
                "type": "image_grid",
                "images": [
                    {
                        "frame_id": f.id,
                        "sequence": f.sequence,
                        "url": f.image_url,
                        "status": f.status,
                        "description": f.description or "",
                        "error_message": f.error_message,
                    }
                    for f in frames
                ],
            },
            {
                "type": "follow_up",
                "message": f"第{frame.sequence}个分镜的图片已更新。继续调整可以直接说具体镜头；满意的话回复「继续」生成视频。",
            },
        ],
        action_type="REGENERATE_FRAME_IMAGE",
        task_id=task_id,
        frame_id=frame.id,
    ))


def _write_frame_video_regeneration_conversation(
    db: Session,
    project: Project,
    frame: Frame,
    task_id: int | None,
) -> None:
    db.add(Conversation(
        project_id=project.id,
        role="assistant",
        content=f"第{frame.sequence}个分镜的视频片段已重新生成。",
        message_type="stage_card",
        stage="video",
        blocks=[
            {
                "type": "follow_up",
                "message": f"第{frame.sequence}个分镜的视频片段已更新。它是单个分镜片段，不是整条成片；如需更新成片，请继续触发整片视频生成。",
            },
        ],
        action_type="REGENERATE_FRAME_VIDEO",
        task_id=task_id,
        frame_id=frame.id,
    ))


def _generate_single_frame_video(project_id: int, frame: Frame, output_dir: str, style: str | None = None) -> dict:
    """在当前线程中为单帧生成视频片段，成功后回填 frame.video_url。失败抛异常。"""
    frame_dir = os.path.join(output_dir, f"frame_{frame.id}_{uuid.uuid4().hex}")
    os.makedirs(frame_dir, exist_ok=True)
    video_path = video_composer.compose_frames(
        [frame],
        frame_dir,
        style=style,
        allow_placeholder_segments=False,
    )
    video_url = _persist_frame_video_segment(project_id, frame, video_path)
    logger.info(f"[视频] frame {frame.sequence} (id={frame.id}) 生成完成: {video_url}")
    return {"frame_id": frame.id, "video_url": video_url}


def _generate_frame_videos_parallel(db: Session, project_id: int, frames: list[Frame], output_dir: str, target_duration: float | None = None, style: str | None = None) -> tuple[str, list[Frame]]:
    frames_to_generate = [frame for frame in frames if _frame_needs_video_generation(frame)]
    skipped_count = len(frames) - len(frames_to_generate)
    if skipped_count:
        logger.info(f"[视频] 跳过 {skipped_count} 个已有视频的帧")

    if not frames_to_generate:
        fresh_frames = _reload_project_frames(db, project_id)
        return _compose_frame_video_urls(fresh_frames, output_dir, target_duration), fresh_frames

    max_workers = min(5, len(frames_to_generate))
    logger.info(f"[视频] ThreadPoolExecutor 并行生成 {len(frames_to_generate)} 帧, max_workers={max_workers}")

    errors: dict[int, Exception] = {}
    generated_segments: list[dict] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_frame = {
            executor.submit(_generate_single_frame_video, project_id, frame, output_dir, style): frame
            for frame in frames_to_generate
        }
        for future in as_completed(future_to_frame):
            frame = future_to_frame[future]
            try:
                generated_segments.append(future.result())
            except Exception as e:
                errors[frame.id] = e
                logger.error(f"[视频] frame {frame.sequence} (id={frame.id}) 生成失败: {e}")

    if errors:
        logger.error(f"[视频] {len(errors)}/{len(frames_to_generate)} 帧生成失败: {list(errors.keys())}")

    frame_map = {frame.id: frame for frame in frames_to_generate}
    for segment in generated_segments:
        frame = frame_map.get(segment["frame_id"])
        if frame:
            frame.video_url = segment["video_url"]
            frame.dirty = 0
    db.flush()

    fresh_frames = _reload_project_frames(db, project_id)
    return _compose_frame_video_urls(fresh_frames, output_dir, target_duration), fresh_frames


def _build_project_audio_track(project: Project, frames: list[Frame]) -> object:
    audio_segments = []
    fallback_used = False
    providers = set()
    warnings = []
    add_tail_padding_seconds = TAIL_PADDING_SECONDS

    for frame in frames:
        text = _resolve_frame_narration_text(frame)
        duration = float(frame.duration or 1.0)
        if not text.strip():
            audio_segments.append(tts_service.create_silent_audio_for_duration(duration))
            providers.add("silent_duration")
            continue

        voice_type = _resolve_frame_voice_type(project, frame)
        tts_result = tts_service.generate_audio(text, voice_type)

        # 以配音实际时长为准：配音比帧长则拉伸帧时长，不截断配音
        tts_duration = ffmpeg_tool.get_audio_duration(tts_result.path)
        if tts_duration > 0 and tts_duration > duration:
            adjusted_duration = min(tts_duration, duration + MAX_TTS_OVERRUN_SECONDS)
            frame.duration = adjusted_duration
            fitted_path = tts_service.fit_audio_to_duration(tts_result.path, adjusted_duration)
            audio_segments.append(fitted_path)
        else:
            fitted_path = tts_service.fit_audio_to_duration(tts_result.path, duration)
            audio_segments.append(fitted_path)

        fallback_used = fallback_used or tts_result.fallback_used
        providers.add(tts_result.provider)
        if tts_result.warning:
            warnings.append(tts_result.warning)

    merged_path = tts_service.concat_audio_clips(audio_segments)
    merged_path = ffmpeg_tool.append_tail_silence(merged_path, add_tail_padding_seconds)
    provider_label = ",".join(sorted(providers)) if providers else "unknown"
    warning = "; ".join(warnings) if warnings else None
    return type(
        "ProjectAudioTrack",
        (),
        {
            "path": merged_path,
            "fallback_used": fallback_used,
            "provider": provider_label,
            "warning": warning,
        },
    )()


def _mark_project_failed(db: Session, project_id: int, stage: str, task_id: str | int | None = None) -> None:
    project = db.execute(select(Project).where(Project.id == project_id)).scalar_one_or_none()
    if project:
        # 只修改状态，不在 helper 内提交；失败处理器统一控制事务边界。
        project_workflow_state.mark_project_stage_failed(project, stage)
        # 确保 last_task_id 指向正确的任务，避免回滚后引用丢失的任务
        if task_id is not None:
            project.last_task_id = task_id


def _update_task_failure_state(
    *,
    task_id: int | None,
    project_id: int | None,
    stage: str | None,
    current_step: str,
    error_code: str,
    error_message: str,
    will_retry: bool,
) -> None:
    # 失败状态统一走这里，避免各个 Celery 任务各自维护一套回写逻辑。
    fail_db = _get_sync_db()
    try:
        if task_id:
            task = generation_task_service.get_task_sync(fail_db, task_id)
            new_retry_count = (task.retry_count or 0) + 1 if will_retry else task.retry_count
            generation_task_service.update_task_sync(
                fail_db,
                task_id,
                status="queued" if will_retry else "failed",
                progress=None if will_retry else 100,
                current_step="RETRYING" if will_retry else current_step,
                error_code=None if will_retry else error_code,
                error_message=error_message,
                retry_count=new_retry_count if will_retry else None,
            )
        # 只有最终失败才标记项目阶段失败；重试中的任务仍保持可恢复状态。
        if project_id is not None and stage and not will_retry:
            _mark_project_failed(fail_db, project_id, stage, task_id=task_id)
            fail_db.commit()
    finally:
        fail_db.close()


@celery_app.task(bind=True, max_retries=3, soft_time_limit=900, time_limit=1200, name="generate_image_task")
def generate_image_task(self, project_id: int, task_id: int | None = None):
    """为图片工作流阶段生成分镜图片。"""
    db = None
    try:
        db = _get_sync_db()
        generation_task_service.start_task_sync(db, task_id, "IMAGE_GENERATING") if task_id else None
        ensure_task_not_cancelled(db, task_id)
        project = db.execute(select(Project).where(Project.id == project_id)).scalar_one()
        project_workflow_state.mark_project_stage_running(project, "image", task_id)
        db.commit()

        frames = list(db.execute(
            select(Frame).where(Frame.project_id == project_id).order_by(Frame.sequence)
        ).scalars())
        if not frames:
            raise ValueError(f"项目 {project_id} 没有帧数据，请先生成剧本")

        # 初始化帧进度追踪（复用提交时的 task_id，确保 generation_tasks 表有记录）
        tracker_task_id = generation_task_tracker.create_task(db, project_id, "image", task_id=task_id)
        all_frame_ids = [f.id for f in frames]
        generation_task_tracker.init_frame_progress(db, tracker_task_id, project_id, all_frame_ids, "image")
        db.commit()

        # 过滤出需要生成的帧（跳过已完成的）
        frames_to_generate = [f for f in frames if not (f.status == 2 and f.image_url)]
        skipped_frame_ids = [f.id for f in frames if f.status == 2 and f.image_url]
        for fid in skipped_frame_ids:
            generation_task_tracker.update_frame_status(db, tracker_task_id, fid, "image", "succeeded")
        if skipped_frame_ids:
            logger.info(f"[image tracker] skipped {len(skipped_frame_ids)} already-completed frames")
            db.commit()

        # 标记待生成帧为 running
        for f in frames_to_generate:
            generation_task_tracker.update_frame_status(db, tracker_task_id, f.id, "image", "running")
        db.commit()

        reference_images = extract_reference_images(project)
        step = generation_task_service.start_step_sync(db, task_id, "IMAGE_GENERATING", progress=10) if task_id else None
        frames = image_generation_service.generate_frame_images(
            frames,
            project_id,
            reference_images=reference_images,
            style=project.style,
        )

        # 更新每帧状态到追踪器
        for frame in frames:
            if frame.id in skipped_frame_ids:
                continue
            if frame.status == 2:
                generation_task_tracker.update_frame_status(
                    db, tracker_task_id, frame.id, "image", "succeeded",
                    result_url=frame.image_url,
                )
            elif frame.status == 3:
                generation_task_tracker.update_frame_status(
                    db, tracker_task_id, frame.id, "image", "failed",
                    error_message=frame.error_message,
                )
        db.commit()

        # 检查帧汇总
        summary = generation_task_tracker.get_frame_summary(db, tracker_task_id, "image")
        failed = [frame.id for frame in frames if frame.status == 3]
        if summary["failed"] > 0:
            generation_task_tracker.fail_task(db, tracker_task_id, "IMAGE_GENERATION_FAILED",
                f"failed frame ids: {failed}")
            generation_task_service.finish_step_sync(
                db,
                step,
                status="failed",
                progress=100,
                output_snapshot={"failed_frame_ids": failed},
                error_message="部分分镜图片生成失败",
            ) if task_id else None
            generation_task_service.update_task_sync(
                db,
                task_id,
                status="failed",
                progress=100,
                current_step="IMAGE_GENERATION_FAILED",
                error_code="IMAGE_GENERATION_FAILED",
                error_message=f"failed frame ids: {failed}",
            ) if task_id else None
            raise RuntimeError(f"IMAGE_GENERATION_FAILED: failed frame ids {failed}")

        generation_task_tracker.complete_task(db, tracker_task_id)

        project_workflow_state.mark_project_stage_review(project, "image", task_id)
        message = build_image_stage_message(frames, task_id)
        db.add(Conversation(
            project_id=project_id,
            role=message["role"],
            content=message["content"],
            message_type=message["message_type"],
            stage=message["stage"],
            blocks=message["blocks"],
            action_type=message["action_type"],
            task_id=message["task_id"],
            metadata_=message["metadata"],
        ))
        db.commit()
        generation_task_service.finish_step_sync(db, step, progress=100, output_snapshot={"frames_count": len(frames)}) if task_id else None
        generation_task_service.update_task_sync(db, task_id, status="succeeded", progress=100, current_step="IMAGE_GENERATED") if task_id else None
    except SoftTimeLimitExceeded as exc:
        logger.error(f"[图片任务超时] project_id={project_id}", exc_info=True)
        will_retry = self.request.retries < self.max_retries
        if db:
            db.rollback()
        try:
            _update_task_failure_state(
                task_id=task_id,
                project_id=project_id,
                stage="image",
                current_step="IMAGE_GENERATION_TIMEOUT",
                error_code="IMAGE_GENERATION_TIMEOUT",
                error_message=str(exc),
                will_retry=will_retry,
            )
        except Exception:
            logger.warning("[failure handler] failed to update image timeout state", exc_info=True)
        if will_retry:
            raise self.retry(exc=exc, countdown=_retry_countdown(self.request.retries))
        raise
    except Exception as exc:
        logger.error(f"[图片任务失败] project_id={project_id}, error={exc}", exc_info=True)
        # 让瞬时错误先走 Celery 重试，重试耗尽后再落最终失败状态。
        will_retry = self.request.retries < self.max_retries
        if db:
            db.rollback()
        try:
            _update_task_failure_state(
                task_id=task_id,
                project_id=project_id,
                stage="image",
                current_step="IMAGE_GENERATION_FAILED",
                error_code="IMAGE_GENERATION_FAILED",
                error_message=str(exc),
                will_retry=will_retry,
            )
        except Exception:
            logger.warning("[failure handler] failed to update image task state", exc_info=True)
        if will_retry:
            raise self.retry(exc=exc, countdown=_retry_countdown(self.request.retries))
        raise
    finally:
        if db:
            db.close()


@celery_app.task(bind=True, max_retries=3, soft_time_limit=3600, time_limit=4500, name="generate_video_task")
def generate_video_task(self, project_id: int, task_id: int | None = None, trigger_source: str = "manual_render"):
    """从分镜图片、配音和合成中生成完整项目视频。"""
    logger.info(f"[任务启动] project_id={project_id}")
    temp_dir = tempfile.mkdtemp()
    db = None
    audio_path = None
    tracker_task_id = None

    try:
        db = _get_sync_db()
        generation_task_service.start_task_sync(db, task_id, "PROJECT_VALIDATION") if task_id else None
        ensure_task_not_cancelled(db, task_id)

        # 创建 generation_tasks 追踪记录（复用提交时的 task_id，避免两套系统 ID 不互通）
        tracker_task_id = generation_task_tracker.create_task(db, project_id, "render", trigger_source, task_id=task_id)
        generation_task_tracker.start_task(db, tracker_task_id, "tts")
        db.commit()

        # ---- Step 1: 读取 frames ----
        step = generation_task_service.start_step_sync(
            db,
            task_id,
            "PROJECT_VALIDATION",
            progress=5,
            input_snapshot={"trigger_source": trigger_source},
        ) if task_id else None
        frames = list(db.execute(
            select(Frame)
            .where(Frame.project_id == project_id)
            .order_by(Frame.sequence)
        ).scalars())
        if not frames:
            raise ValueError(f"项目 {project_id} 没有帧数据，请先生成剧本")

        project = db.execute(select(Project).where(Project.id == project_id)).scalar_one()
        project_workflow_state.mark_project_stage_running(project, "video", task_id)
        db.commit()
        generation_task_service.finish_step_sync(
            db,
            step,
            progress=10,
            output_snapshot={"frames_count": len(frames), "trigger_source": trigger_source},
        ) if task_id else None
        generation_task_service.update_task_sync(db, task_id, progress=10, current_step="PROJECT_VALIDATION") if task_id else None
        generation_task_tracker.update_stage(db, tracker_task_id, "tts", 10)
        db.commit()
        logger.info(f"[读取帧] project_id={project_id}, frames={len(frames)}")

        # ---- Step 2: TTS 配音生成 ----
        step = generation_task_service.start_step_sync(db, task_id, "TTS_GENERATING", progress=10) if task_id else None
        logger.info("[TTS] 开始生成配音...")
        tts_result = _build_project_audio_track(project, frames)
        audio_path = tts_result.path
        allow_degraded_audio = ALLOW_DEGRADED_AUDIO
        if tts_result.fallback_used and not allow_degraded_audio:
            generation_task_tracker.fail_task(db, tracker_task_id, "TTS_GENERATION_FAILED", f"tts fallback used: {tts_result.warning}")
            db.commit()
            raise GenerationStageError(
                stage="video",
                current_step="TTS_GENERATION_FAILED",
                error_code="TTS_GENERATION_FAILED",
                message=f"tts fallback used: {tts_result.warning}",
            )

        # 上传配音到 TOS，存入 project.audio_url
        audio_object = f"projects/{project_id}/audio.mp3"
        audio_url = get_storage_client().upload_file(audio_path, audio_object)
        project.audio_url = audio_url
        db.commit()
        generation_task_service.finish_step_sync(
            db,
            step,
            progress=25,
            output_snapshot={
                "audio_url": audio_url,
                "provider": tts_result.provider,
                "fallback_used": tts_result.fallback_used,
                "warning": tts_result.warning,
                "trigger_source": trigger_source,
            },
        ) if task_id else None
        generation_task_service.update_task_sync(db, task_id, progress=25, current_step="TTS_GENERATING") if task_id else None
        generation_task_tracker.update_stage(db, tracker_task_id, "image", 25)
        db.commit()
        logger.info(f"[TTS] 项目级配音完成: {audio_object}")

        # ---- Step 3: 为每个分镜生成图片 ----
        step = generation_task_service.start_step_sync(db, task_id, "IMAGE_GENERATING", progress=30) if task_id else None
        logger.info("[图片] 开始生成帧配图...")

        # 初始化帧进度追踪
        all_frame_ids = [f.id for f in frames]
        generation_task_tracker.init_frame_progress(db, tracker_task_id, project_id, all_frame_ids, "image")

        # 跳过已完成的帧，记录哪些帧需要重新生成
        frames_needing_image = []
        for f in frames:
            if f.status == 2 and f.image_url:
                generation_task_tracker.update_frame_status(db, tracker_task_id, f.id, "image", "succeeded", result_url=f.image_url)
            else:
                generation_task_tracker.update_frame_status(db, tracker_task_id, f.id, "image", "running")
                frames_needing_image.append(f)
        db.commit()

        reference_images = extract_reference_images(project)
        frames = image_generation_service.generate_frame_images(
            frames,
            project_id,
            reference_images=reference_images,
            style=project.style,
        )

        # 更新帧状态
        for f in frames:
            if f.status == 2:
                generation_task_tracker.update_frame_status(db, tracker_task_id, f.id, "image", "succeeded", result_url=f.image_url)
            elif f.status == 3:
                generation_task_tracker.update_frame_status(db, tracker_task_id, f.id, "image", "failed", error_message=f.error_message)
        db.commit()

        failed_images = [f.id for f in frames if f.status == 3]
        generation_task_service.finish_step_sync(db, step, status="failed" if failed_images else "succeeded", progress=45, output_snapshot={"failed_frame_ids": failed_images}, error_message="部分分镜图片生成失败" if failed_images else None) if task_id else None
        generation_task_service.update_task_sync(db, task_id, progress=45, current_step="IMAGE_GENERATING") if task_id else None
        if failed_images:
            generation_task_tracker.fail_task(db, tracker_task_id, "IMAGE_GENERATION_FAILED", f"failed frame ids: {failed_images}")
            db.commit()
            raise GenerationStageError(
                stage="image",
                current_step="IMAGE_GENERATION_FAILED",
                error_code="IMAGE_GENERATION_FAILED",
                message=f"failed frame ids: {failed_images}",
            )
        generation_task_tracker.update_stage(db, tracker_task_id, "video", 45)
        db.commit()
        logger.info(f"[image] completed frames: {len(frames)}")

        # 图片生成完成后写入 image_grid 快照消息，确保对话中保留本次图片版本
        if frames_needing_image:
            image_msg = build_image_stage_message(frames, task_id)
            db.add(Conversation(
                project_id=project_id,
                role=image_msg["role"],
                content=image_msg["content"],
                message_type=image_msg["message_type"],
                stage=image_msg["stage"],
                blocks=image_msg["blocks"],
                action_type=image_msg["action_type"],
                task_id=image_msg["task_id"],
                metadata_=image_msg["metadata"],
            ))
            db.commit()

        # ---- Step 4+5: 为每个分镜生成视频并拼接 ----
        step = generation_task_service.start_step_sync(db, task_id, "VIDEO_GENERATING", progress=50) if task_id else None
        logger.info("[视频] 开始生成帧视频...")

        # 初始化视频帧进度追踪
        generation_task_tracker.init_frame_progress(db, tracker_task_id, project_id, all_frame_ids, "video")
        for f in frames:
            generation_task_tracker.update_frame_status(db, tracker_task_id, f.id, "video", "running")
        db.commit()

        output_dir = os.path.join(temp_dir, f"project_{project_id}")

        video_path, frames = _generate_frame_videos_parallel(
            db,
            project_id,
            frames,
            output_dir,
            target_duration=project.target_duration,
            style=project.style,
        )

        # 更新视频帧状态
        for f in frames:
            if f.video_url and str(f.video_url).startswith("http"):
                generation_task_tracker.update_frame_status(db, tracker_task_id, f.id, "video", "succeeded", result_url=f.video_url)
            else:
                generation_task_tracker.update_frame_status(db, tracker_task_id, f.id, "video", "failed")
        db.commit()

        failed_videos = [f.id for f in frames if f.status == 3]
        generation_task_service.finish_step_sync(db, step, status="failed" if failed_videos else "succeeded", progress=75, output_snapshot={"failed_frame_ids": failed_videos}, error_message="部分分镜视频生成失败" if failed_videos else None) if task_id else None
        generation_task_service.update_task_sync(db, task_id, progress=75, current_step="VIDEO_GENERATING") if task_id else None
        if failed_videos:
            generation_task_tracker.fail_task(db, tracker_task_id, "VIDEO_SEGMENT_GENERATION_FAILED", f"failed frame ids: {failed_videos}")
            db.commit()
            raise GenerationStageError(
                stage="video",
                current_step="VIDEO_SEGMENT_GENERATION_FAILED",
                error_code="VIDEO_SEGMENT_GENERATION_FAILED",
                message=f"failed frame ids: {failed_videos}",
            )

        # ---- Step 5.5: 合并 TTS 音频到视频 ----
        generation_task_tracker.update_stage(db, tracker_task_id, "audio_mix", 78)
        db.commit()
        step = generation_task_service.start_step_sync(db, task_id, "AUDIO_MIXING", progress=78) if task_id else None
        if audio_path and os.path.exists(audio_path):
            try:
                merged_path = os.path.join(output_dir, "merged_output.mp4")
                ffmpeg_tool.replace_audio(video_path, audio_path, merged_path)
                video_path = merged_path
                logger.info("[音频合并] TTS 配音已合并到视频")
                generation_task_service.finish_step_sync(db, step, progress=85, output_snapshot={"merged": True}) if task_id else None
            except Exception as e:
                logger.warning(f"[音频合并] 合并失败，降级上传无声视频: {e}")
                generation_task_service.finish_step_sync(db, step, status="failed", progress=85, error_message=str(e)) if task_id else None
        else:
            logger.warning("[audio] no TTS audio file, skip merging")
            generation_task_service.finish_step_sync(db, step, status="skipped", progress=85, error_message="no audio file") if task_id else None

        # ---- Step 5.6: BGM 选曲并混入视频 ----
        generation_task_tracker.update_stage(db, tracker_task_id, "bgm_mix", 86)
        db.commit()
        step = generation_task_service.start_step_sync(db, task_id, "BGM_MIXING", progress=86) if task_id else None
        try:
            # 读取最新剧本内容
            script_result = db.execute(
                select(Script).where(Script.project_id == project_id).order_by(Script.version.desc()).limit(1)
            )
            script = script_result.scalar_one_or_none()
            script_content = script.content if script and script.content else {}

            music_config = dict(getattr(project, "music_config", None) or {})
            current_bgm_id = music_config.get("current_bgm_id")
            bgm_id = int(current_bgm_id) if current_bgm_id else bgm_selector_service.select_bgm(db, script_content)
            if bgm_id and not current_bgm_id:
                music_config["current_bgm_id"] = int(bgm_id)
                project.music_config = music_config
            if bgm_id:
                bgm_asset = AssetDAO.get_asset_by_id(db, bgm_id)
                if bgm_asset and bgm_asset.url:
                    # 判断是本地路径还是远程 URL
                    from backend import PROJECT_ROOT
                    bgm_url = bgm_asset.url
                    if bgm_url.startswith(("http://", "https://")):
                        import urllib.request
                        bgm_local = os.path.join(temp_dir, "bgm.mp3")
                        urllib.request.urlretrieve(bgm_url, bgm_local)
                    else:
                        # 本地相对路径，相对于项目根目录解析
                        bgm_local = str(PROJECT_ROOT / bgm_url)
                    if os.path.exists(bgm_local):
                        bgm_output = os.path.join(output_dir, "bgm_output.mp4")
                        ffmpeg_tool.add_bgm(video_path, bgm_local, bgm_output, bgm_volume=0.3, original_volume=1.0)
                        video_path = bgm_output
                        logger.info("[BGM] 背景音乐已混入视频: %s", bgm_asset.title)
                        generation_task_service.finish_step_sync(
                            db, step, progress=88,
                            output_snapshot={"bgm_id": bgm_id, "bgm_title": bgm_asset.title}
                        ) if task_id else None
                    else:
                        logger.warning("[BGM] BGM 文件下载失败，跳过混音")
                        generation_task_service.finish_step_sync(db, step, status="skipped", progress=88) if task_id else None
                else:
                    logger.warning("[BGM] BGM 资产不存在或无 URL，跳过混音")
                    generation_task_service.finish_step_sync(db, step, status="skipped", progress=88) if task_id else None
            else:
                logger.info("[BGM] 无合适 BGM，跳过混音")
                generation_task_service.finish_step_sync(db, step, status="skipped", progress=88) if task_id else None
        except Exception as e:
            logger.warning("[BGM] 选曲/混音失败，降级上传无 BGM 视频: %s", e)
            generation_task_service.finish_step_sync(
                db, step, status="failed", progress=88, error_message=str(e)
            ) if task_id else None

        # 上传成品视频到 TOS
        generation_task_tracker.update_stage(db, tracker_task_id, "output", 88)
        db.commit()
        step = generation_task_service.start_step_sync(db, task_id, "OUTPUT_UPLOADING", progress=88) if task_id else None
        output_task_key = task_id or uuid.uuid4().hex
        video_object = f"projects/{project_id}/outputs/{output_task_key}/output.mp4"
        video_url = get_storage_client().upload_file(video_path, video_object)

        db.commit()
        generation_task_service.finish_step_sync(db, step, progress=95, output_snapshot={"video_url": video_url}) if task_id else None
        logger.info(f"[视频] 完成: {video_object}")

        # ---- Step 6: 储存最终项目状态----
        project.video_output_url = video_url
        for frame in frames:
            frame.dirty = 0
        project_workflow_state.mark_project_stage_review(project, "video", task_id)
        db.add(Conversation(
            project_id=project_id,
            role="assistant",
            content="视频阶段已完成。你可以预览成片，确认完成或继续提出修改意见。",
            message_type="stage_card",
            stage="video",
            blocks=build_video_stage_blocks(project, video_url=video_url, task_id=task_id),
            action_type="GENERATE_VIDEO",
            task_id=task_id,
        ))
        db.commit()
        generation_task_service.update_task_sync(db, task_id, status="succeeded", progress=100, current_step="COMPLETED") if task_id else None
        generation_task_tracker.complete_task(db, tracker_task_id)
        db.commit()
        logger.info(f"[完成] project_id={project_id}, 视频已生成: {video_object}")

    except SoftTimeLimitExceeded as exc:
        logger.error(f"[视频任务超时] project_id={project_id}", exc_info=True)
        will_retry = self.request.retries < self.max_retries
        if db:
            db.rollback()
        try:
            _update_task_failure_state(
                task_id=task_id,
                project_id=project_id,
                stage="video",
                current_step="VIDEO_GENERATION_TIMEOUT",
                error_code="VIDEO_GENERATION_TIMEOUT",
                error_message=str(exc),
                will_retry=will_retry,
            )
            # 更新 generation_tasks 追踪表
            if tracker_task_id:
                fail_db = _get_sync_db()
                try:
                    generation_task_tracker.fail_task(fail_db, tracker_task_id, "VIDEO_GENERATION_TIMEOUT", str(exc))
                    fail_db.commit()
                except Exception:
                    fail_db.rollback()
                finally:
                    fail_db.close()
        except Exception:
            logger.warning("[failure handler] failed to update video timeout state", exc_info=True)
        if will_retry:
            raise self.retry(exc=exc, countdown=_retry_countdown(self.request.retries))
        raise
    except Exception as exc:
        logger.error(f"[失败] project_id={project_id}, error={exc}", exc_info=True)
        will_retry = self.request.retries < self.max_retries
        if db:
            db.rollback()
        try:
            # 这里即使状态回写再次出错，也不要覆盖原始业务异常。
            _update_task_failure_state(
                task_id=task_id,
                project_id=project_id,
                stage=getattr(exc, "stage", "video"),
                current_step=getattr(exc, "current_step", "FAILED"),
                error_code=getattr(exc, "error_code", "VIDEO_GENERATION_FAILED"),
                error_message=str(exc),
                will_retry=will_retry,
            )
            # 更新 generation_tasks 追踪表
            if tracker_task_id:
                fail_db = _get_sync_db()
                try:
                    generation_task_tracker.fail_task(fail_db, tracker_task_id, getattr(exc, "error_code", "VIDEO_GENERATION_FAILED"), str(exc))
                    fail_db.commit()
                except Exception:
                    fail_db.rollback()
                finally:
                    fail_db.close()
        except Exception:
            logger.warning("[failure handler] failed to update task state", exc_info=True)
        if will_retry:
            raise self.retry(exc=exc, countdown=_retry_countdown(self.request.retries))
        raise exc

    finally:
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except OSError:
                pass
        if db:
            db.close()
        # 清理临时目录
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


@celery_app.task(bind=True, max_retries=3, soft_time_limit=900, time_limit=1200, name="generate_project_tts_task")
def generate_project_tts_task(self, project_id: int, task_id: int | None = None):
    """Regenerate project-level TTS audio without rendering images or video."""
    logger.info("[TTS task] start project_id=%s", project_id)
    db = None
    audio_path = None

    try:
        db = _get_sync_db()
        generation_task_service.start_task_sync(db, task_id, "TTS_GENERATING") if task_id else None
        ensure_task_not_cancelled(db, task_id)

        step = generation_task_service.start_step_sync(
            db,
            task_id,
            "TTS_GENERATING",
            progress=10,
            input_snapshot={"trigger_source": "chat_tts_regeneration"},
        ) if task_id else None

        project = db.execute(select(Project).where(Project.id == project_id)).scalar_one_or_none()
        if not project:
            raise ValueError(f"project not found: {project_id}")
        frames = list(db.execute(
            select(Frame)
            .where(Frame.project_id == project_id)
            .order_by(Frame.sequence)
        ).scalars())
        if not frames:
            raise ValueError(f"project {project_id} has no frames for TTS regeneration")

        project_workflow_state.mark_project_stage_running(project, "video", task_id)
        db.commit()

        tts_result = _build_project_audio_track(project, frames)
        audio_path = tts_result.path
        if tts_result.fallback_used and not ALLOW_DEGRADED_AUDIO:
            raise GenerationStageError(
                stage="video",
                current_step="TTS_GENERATION_FAILED",
                error_code="TTS_GENERATION_FAILED",
                message=f"tts fallback used: {tts_result.warning}",
            )

        audio_object = f"projects/{project_id}/audio.mp3"
        audio_url = get_storage_client().upload_file(audio_path, audio_object)
        project.audio_url = audio_url
        project.dirty_stage = "video"
        project_workflow_state.mark_project_stage_review(project, "video", task_id)
        db.commit()

        generation_task_service.finish_step_sync(
            db,
            step,
            progress=95,
            output_snapshot={
                "audio_url": audio_url,
                "provider": tts_result.provider,
                "fallback_used": tts_result.fallback_used,
                "warning": tts_result.warning,
            },
        ) if task_id else None
        generation_task_service.update_task_sync(db, task_id, status="succeeded", progress=100, current_step="COMPLETED") if task_id else None
        logger.info("[TTS task] completed project_id=%s audio=%s", project_id, audio_object)

    except SoftTimeLimitExceeded as exc:
        logger.error("[TTS task] timeout project_id=%s", project_id, exc_info=True)
        will_retry = self.request.retries < self.max_retries
        if db:
            db.rollback()
        try:
            _update_task_failure_state(
                task_id=task_id,
                project_id=project_id,
                stage="video",
                current_step="TTS_GENERATION_TIMEOUT",
                error_code="TTS_GENERATION_TIMEOUT",
                error_message=str(exc),
                will_retry=will_retry,
            )
        except Exception:
            logger.warning("[failure handler] failed to update TTS timeout state", exc_info=True)
        if will_retry:
            raise self.retry(exc=exc, countdown=_retry_countdown(self.request.retries))
        raise
    except Exception as exc:
        logger.error("[TTS task] failed project_id=%s error=%s", project_id, exc, exc_info=True)
        will_retry = self.request.retries < self.max_retries
        if db:
            db.rollback()
        try:
            _update_task_failure_state(
                task_id=task_id,
                project_id=project_id,
                stage=getattr(exc, "stage", "video"),
                current_step=getattr(exc, "current_step", "TTS_GENERATION_FAILED"),
                error_code=getattr(exc, "error_code", "TTS_GENERATION_FAILED"),
                error_message=str(exc),
                will_retry=will_retry,
            )
        except Exception:
            logger.warning("[failure handler] failed to update TTS task state", exc_info=True)
        if will_retry:
            raise self.retry(exc=exc, countdown=_retry_countdown(self.request.retries))
        raise exc
    finally:
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except OSError:
                pass
        if db:
            db.close()


@celery_app.task(bind=True, max_retries=3, soft_time_limit=180, time_limit=300, name="generate_frame_image_task")
def generate_frame_image_task(self, project_id: int, frame_id: int, task_id: int | None = None):
    """重新生成单帧图片，不合成完整视频。"""
    db = None
    try:
        db = _get_sync_db()
        generation_task_service.start_task_sync(db, task_id, "FRAME_IMAGE_GENERATING") if task_id else None
        ensure_task_not_cancelled(db, task_id)
        step = generation_task_service.start_step_sync(
            db, task_id, "FRAME_IMAGE_GENERATING", progress=10, frame_id=frame_id
        ) if task_id else None
        frame = db.execute(
            select(Frame).where(Frame.id == frame_id, Frame.project_id == project_id)
        ).scalar_one()
        # 记录任务开始时的版本号，用于完成后校验
        frame_version_at_start = frame.version or 1
        project = db.execute(select(Project).where(Project.id == project_id)).scalar_one()
        reference_images = extract_reference_images(project)
        frame.image_url = None
        frame.status = 0
        frames = image_generation_service.generate_frame_images(
            [frame],
            project_id,
            reference_images=reference_images,
            style=project.style,
        )
        db.commit()

        # 版本校验：如果任务期间帧被用户编辑过，丢弃本次结果
        frame_current = db.execute(
            select(Frame).where(Frame.id == frame_id)
        ).scalar_one()
        if (frame_current.version or 1) != frame_version_at_start:
            logger.warning(
                f"[单帧图片任务] 帧 {frame_id} 在任务期间被编辑（版本 {frame_version_at_start} -> {frame_current.version}），丢弃本次结果"
            )
            generation_task_service.finish_step_sync(
                db, step, status="skipped", progress=100,
                output_snapshot={"skipped": True, "reason": "frame_edited_during_task"},
            ) if task_id else None
            generation_task_service.update_task_sync(
                db, task_id, status="succeeded", progress=100, current_step="FRAME_IMAGE_SKIPPED",
            ) if task_id else None
            db.commit()
            return

        failed = [item.id for item in frames if item.status == 3]
        if failed:
            generation_task_service.finish_step_sync(
                db, step, status="failed", progress=100, output_snapshot={"failed_frame_ids": failed},
                error_message=frame.error_message,
            ) if task_id else None
            generation_task_service.update_task_sync(
                db, task_id, status="failed", progress=100, current_step="FRAME_IMAGE_FAILED",
                error_code="FRAME_IMAGE_FAILED", error_message=frame.error_message,
            ) if task_id else None
            raise RuntimeError(frame.error_message or "frame image generation failed")
        frame.dirty = 0
        generation_task_service.finish_step_sync(
            db, step, progress=100, output_snapshot={"image_url": frame.image_url}
        ) if task_id else None
        generation_task_service.update_task_sync(
            db, task_id, status="succeeded", progress=100, current_step="FRAME_IMAGE_GENERATED",
            current_frame_id=frame_id,
        ) if task_id else None
        project = db.execute(select(Project).where(Project.id == project_id)).scalar_one()
        _write_frame_image_regeneration_conversation(db, project, frame, task_id)
        db.commit()
    except SoftTimeLimitExceeded as exc:
        logger.error(f"[单帧图片任务超时] project_id={project_id}, frame_id={frame_id}", exc_info=True)
        will_retry = self.request.retries < self.max_retries
        if db:
            db.rollback()
        try:
            _update_task_failure_state(
                task_id=task_id,
                project_id=project_id,
                stage="image",
                current_step="FRAME_IMAGE_TIMEOUT",
                error_code="FRAME_IMAGE_TIMEOUT",
                error_message=str(exc),
                will_retry=will_retry,
            )
        except Exception:
            logger.warning("[failure handler] failed to update frame image timeout state", exc_info=True)
        if will_retry:
            raise self.retry(exc=exc, countdown=_retry_countdown(self.request.retries))
        raise
    except Exception as exc:
        logger.error(f"[单帧图片任务失败] project_id={project_id}, frame_id={frame_id}, error={exc}", exc_info=True)
        will_retry = self.request.retries < self.max_retries
        if db:
            db.rollback()
        try:
            _update_task_failure_state(
                task_id=task_id,
                project_id=project_id,
                stage="image",
                current_step="FRAME_IMAGE_FAILED",
                error_code="FRAME_IMAGE_FAILED",
                error_message=str(exc),
                will_retry=will_retry,
            )
        except Exception:
            logger.warning("[failure handler] failed to update frame image task state", exc_info=True)
        if will_retry:
            raise self.retry(exc=exc, countdown=_retry_countdown(self.request.retries))
        raise
    finally:
        if db:
            db.close()


@celery_app.task(bind=True, max_retries=3, soft_time_limit=600, time_limit=720, name="generate_frame_video_task")
def generate_frame_video_task(self, project_id: int, frame_id: int, task_id: int | None = None):
    """重新生成单帧视频片段并记录任务输出。"""
    temp_dir = tempfile.mkdtemp()
    db = None
    try:
        db = _get_sync_db()
        generation_task_service.start_task_sync(db, task_id, "FRAME_VIDEO_GENERATING") if task_id else None
        ensure_task_not_cancelled(db, task_id)
        step = generation_task_service.start_step_sync(
            db, task_id, "FRAME_VIDEO_GENERATING", progress=10, frame_id=frame_id
        ) if task_id else None
        frame = db.execute(
            select(Frame).where(Frame.id == frame_id, Frame.project_id == project_id)
        ).scalar_one()
        project = db.execute(select(Project).where(Project.id == project_id)).scalar_one()
        output_dir = os.path.join(temp_dir, f"project_{project_id}_frame_{frame_id}")
        video_path = video_composer.compose_frames(
            [frame],
            output_dir,
            style=project.style,
            allow_placeholder_segments=False,
        )
        object_key = f"projects/{project_id}/frames/frame_{frame_id}.mp4"
        video_url = get_storage_client().upload_file(video_path, object_key)
        # 单帧视频产物写入 video_url，避免覆盖帧配音/音效 URL。
        frame.video_url = video_url
        frame.dirty = 0
        project.dirty_stage = None
        project.stage_status = "awaiting_review"
        db.commit()
        generation_task_service.finish_step_sync(
            db, step, progress=100, output_snapshot={"video_url": video_url}
        ) if task_id else None
        generation_task_service.update_task_sync(
            db, task_id, status="succeeded", progress=100, current_step="FRAME_VIDEO_GENERATED",
            current_frame_id=frame_id,
        ) if task_id else None
        _write_frame_video_regeneration_conversation(db, project, frame, task_id)
        db.commit()
    except SoftTimeLimitExceeded as exc:
        logger.error(f"[单帧视频任务超时] project_id={project_id}, frame_id={frame_id}", exc_info=True)
        will_retry = self.request.retries < self.max_retries
        if db:
            db.rollback()
        try:
            _update_task_failure_state(
                task_id=task_id,
                project_id=project_id,
                stage="video",
                current_step="FRAME_VIDEO_TIMEOUT",
                error_code="FRAME_VIDEO_TIMEOUT",
                error_message=str(exc),
                will_retry=will_retry,
            )
        except Exception:
            logger.warning("[failure handler] failed to update frame video timeout state", exc_info=True)
        if will_retry:
            raise self.retry(exc=exc, countdown=_retry_countdown(self.request.retries))
        raise
    except Exception as exc:
        logger.error(f"[单帧视频任务失败] project_id={project_id}, frame_id={frame_id}, error={exc}", exc_info=True)
        will_retry = self.request.retries < self.max_retries
        if db:
            db.rollback()
        try:
            _update_task_failure_state(
                task_id=task_id,
                project_id=project_id,
                stage="video",
                current_step="FRAME_VIDEO_FAILED",
                error_code="FRAME_VIDEO_FAILED",
                error_message=str(exc),
                will_retry=will_retry,
            )
        except Exception:
            logger.warning("[failure handler] failed to update frame video task state", exc_info=True)
        if will_retry:
            raise self.retry(exc=exc, countdown=_retry_countdown(self.request.retries))
        raise
    finally:
        if db:
            db.close()
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


