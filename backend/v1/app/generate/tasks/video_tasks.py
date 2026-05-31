"""基于分镜帧的 Celery 视频生成任务。"""
import os
import logging
import tempfile
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
from backend.ffmpeg import ffmpeg_tool
from backend.v1.app.generate.service.stages.music_service import music_generation_service
from backend.v1.app.generate.service.generateUtils.task_service import generation_task_service
from backend.v1.app.generate.service.workflow.blocks import build_video_stage_blocks
from backend.v1.app.generate.service.stages.image_workflow import build_image_stage_message
from backend.v1.app.generate.service.workflow import state as project_workflow_state
from backend.v1.app.models.conversation import Conversation
from backend.store.obj.factory import get_storage_client

logger = logging.getLogger(__name__)


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
    frame.video_url = video_url
    frame.dirty = 0
    return video_url


def _resolve_frame_narration_text(frame: Frame) -> str:
    ai_params = frame.ai_params or {}
    return (getattr(frame, "narration", None) or ai_params.get("text") or frame.description or "").strip()


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


def _build_project_audio_track(project: Project, frames: list[Frame]) -> object:
    audio_segments = []
    fallback_used = False
    providers = set()
    warnings = []

    for frame in frames:
        text = _resolve_frame_narration_text(frame)
        duration = float(frame.duration or 1.0)
        if not text.strip():
            audio_segments.append(tts_service.create_silent_audio_for_duration(duration))
            providers.add("silent_duration")
            continue

        voice_type = _resolve_frame_voice_type(project, frame)
        tts_result = tts_service.generate_audio(text, voice_type)
        fitted_path = tts_service.fit_audio_to_duration(tts_result.path, duration)
        audio_segments.append(fitted_path)
        fallback_used = fallback_used or tts_result.fallback_used
        providers.add(tts_result.provider)
        if tts_result.warning:
            warnings.append(tts_result.warning)

    merged_path = tts_service.concat_audio_clips(audio_segments)
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


def _mark_project_failed(db: Session, project_id: int, stage: str) -> None:
    project = db.execute(select(Project).where(Project.id == project_id)).scalar_one_or_none()
    if project:
        # 只修改状态，不在 helper 内提交；失败处理器统一控制事务边界。
        project_workflow_state.mark_project_stage_failed(project, stage)


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
            if will_retry:
                task.retry_count = (task.retry_count or 0) + 1
            generation_task_service.update_task_sync(
                fail_db,
                task_id,
                status="queued" if will_retry else "failed",
                progress=None if will_retry else 100,
                current_step="RETRYING" if will_retry else current_step,
                error_code=None if will_retry else error_code,
                error_message=error_message,
            )
        # 只有最终失败才标记项目阶段失败；重试中的任务仍保持可恢复状态。
        if project_id is not None and stage and not will_retry:
            _mark_project_failed(fail_db, project_id, stage)
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
            raise ValueError(f"椤圭洰 {project_id} 娌℃湁甯ф暟鎹紝璇峰厛鐢熸垚鍓ф湰")

        reference_images = extract_reference_images(project)
        step = generation_task_service.start_step_sync(db, task_id, "IMAGE_GENERATING", progress=10) if task_id else None
        frames = image_generation_service.generate_frame_images(
            frames,
            project_id,
            reference_images=reference_images,
        )
        db.commit()
        failed = [frame.id for frame in frames if frame.status == 3]
        if failed:
            generation_task_service.finish_step_sync(
                db,
                step,
                status="failed",
                progress=100,
                output_snapshot={"failed_frame_ids": failed},
                error_message="閮ㄥ垎鍒嗛暅鍥剧墖鐢熸垚澶辫触",
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
        logger.error(f"[鍥剧墖浠诲姟瓒呮椂] project_id={project_id}", exc_info=True)
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
        logger.error(f"[鍥剧墖浠诲姟澶辫触] project_id={project_id}, error={exc}", exc_info=True)
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
    logger.info(f"[浠诲姟鍚姩] project_id={project_id}")
    temp_dir = tempfile.mkdtemp()
    db = None
    audio_path = None

    try:
        db = _get_sync_db()
        generation_task_service.start_task_sync(db, task_id, "PROJECT_VALIDATION") if task_id else None
        ensure_task_not_cancelled(db, task_id)

        # ---- Step 1: 璇诲彇 frames ----
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
            raise ValueError(f"椤圭洰 {project_id} 娌℃湁甯ф暟鎹紝璇峰厛鐢熸垚鍓ф湰")

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
        logger.info(f"[璇诲彇甯 project_id={project_id}, frames={len(frames)}")

        # ---- Step 2: TTS 配音生成 ----
        step = generation_task_service.start_step_sync(db, task_id, "TTS_GENERATING", progress=10) if task_id else None
        logger.info("[TTS] 寮€濮嬬敓鎴愰厤闊?..")
        tts_result = _build_project_audio_track(project, frames)
        audio_path = tts_result.path
        allow_degraded_audio = ALLOW_DEGRADED_AUDIO
        if tts_result.fallback_used and not allow_degraded_audio:
            raise GenerationStageError(
                stage="video",
                current_step="TTS_GENERATION_FAILED",
                error_code="TTS_GENERATION_FAILED",
                message=f"tts fallback used: {tts_result.warning}",
            )

        # 涓婁紶閰嶉煶鍒?TOS锛屽瓨鍏?project.audio_url
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
        logger.info(f"[TTS] 椤圭洰绾ч厤闊冲畬鎴? {audio_object}")

        # ---- Step 3: 为每个分镜生成图片 ----
        step = generation_task_service.start_step_sync(db, task_id, "IMAGE_GENERATING", progress=30) if task_id else None
        logger.info("[鍥剧墖] 寮€濮嬬敓鎴愬抚閰嶅浘...")
        reference_images = extract_reference_images(project)
        frames = image_generation_service.generate_frame_images(
            frames,
            project_id,
            reference_images=reference_images,
        )
        db.commit()
        failed_images = [f.id for f in frames if f.status == 3]
        generation_task_service.finish_step_sync(db, step, status="failed" if failed_images else "succeeded", progress=45, output_snapshot={"failed_frame_ids": failed_images}, error_message="閮ㄥ垎鍒嗛暅鍥剧墖鐢熸垚澶辫触" if failed_images else None) if task_id else None
        generation_task_service.update_task_sync(db, task_id, progress=45, current_step="IMAGE_GENERATING") if task_id else None
        if failed_images:
            raise GenerationStageError(
                stage="image",
                current_step="IMAGE_GENERATION_FAILED",
                error_code="IMAGE_GENERATION_FAILED",
                message=f"failed frame ids: {failed_images}",
            )
        logger.info(f"[image] completed frames: {len(frames)}")

        # ---- Step 4+5: 为每个分镜生成视频并拼接 ----
        step = generation_task_service.start_step_sync(db, task_id, "VIDEO_GENERATING", progress=50) if task_id else None
        logger.info("[瑙嗛] 寮€濮嬬敓鎴愬抚瑙嗛...")
        output_dir = os.path.join(temp_dir, f"project_{project_id}")

        def _persist_segment(frame: Frame, segment_path: str) -> None:
            _persist_frame_video_segment(project_id, frame, segment_path)
            db.commit()

        video_path = video_composer.compose_frames(
            frames,
            output_dir,
            target_duration=project.target_duration,
            allow_placeholder_segments=False,
            on_segment_ready=_persist_segment,
        )
        failed_videos = [f.id for f in frames if f.status == 3]
        generation_task_service.finish_step_sync(db, step, status="failed" if failed_videos else "succeeded", progress=75, output_snapshot={"failed_frame_ids": failed_videos}, error_message="閮ㄥ垎鍒嗛暅瑙嗛鐢熸垚澶辫触" if failed_videos else None) if task_id else None
        generation_task_service.update_task_sync(db, task_id, progress=75, current_step="VIDEO_GENERATING") if task_id else None
        if failed_videos:
            raise GenerationStageError(
                stage="video",
                current_step="VIDEO_SEGMENT_GENERATION_FAILED",
                error_code="VIDEO_SEGMENT_GENERATION_FAILED",
                message=f"failed frame ids: {failed_videos}",
            )

        # ---- Step 5.5: 合并 TTS 音频到视频 ----
        step = generation_task_service.start_step_sync(db, task_id, "AUDIO_MIXING", progress=78) if task_id else None
        if audio_path and os.path.exists(audio_path):
            try:
                merged_path = os.path.join(output_dir, "merged_output.mp4")
                ffmpeg_tool.replace_audio(video_path, audio_path, merged_path)
                video_path = merged_path
                logger.info("[闊抽鍚堝苟] TTS 閰嶉煶宸插悎骞跺埌瑙嗛")
                generation_task_service.finish_step_sync(db, step, progress=85, output_snapshot={"merged": True}) if task_id else None
            except Exception as e:
                logger.warning(f"[闊抽鍚堝苟] 鍚堝苟澶辫触锛岄檷绾т笂浼犳棤澹拌棰? {e}")
                generation_task_service.finish_step_sync(db, step, status="failed", progress=85, error_message=str(e)) if task_id else None
        else:
            logger.warning("[audio] no TTS audio file, skip merging")
            generation_task_service.finish_step_sync(db, step, status="skipped", progress=85, error_message="no audio file") if task_id else None

        # ---- Step 5.6: 生成 BGM 并混入视频（暂时禁用，接口保留） ----
        # bgm_desc = (frames[0].ai_params or {}).get("bgm", "")
        # if bgm_desc:
        #     bgm_path = music_generation_service.generate_bgm(bgm_desc)
        #     if bgm_path and os.path.exists(bgm_path):
        #         try:
        #             bgm_output = os.path.join(output_dir, "bgm_output.mp4")
        #             ffmpeg_tool.add_bgm(video_path, bgm_path, bgm_output, bgm_volume=0.3, original_volume=1.0)
        #             video_path = bgm_output
        #             logger.info("[BGM] 背景音乐已混入视频")
        #         except Exception as e:
        #             logger.warning(f"[BGM] 混音失败，降级上传无 BGM 视频: {e}")
        #         finally:
        #             try:
        #                 os.remove(bgm_path)
        #             except OSError:
        #                 pass
        #     else:
        #         logger.warning("[BGM] BGM 鐢熸垚澶辫触锛岃烦杩囨贩闊?)
        # else:
        #     logger.info("[BGM] 鏃?BGM 鎻忚堪锛岃烦杩囩敓鎴?)

        # 上传成品视频到 TOS
        step = generation_task_service.start_step_sync(db, task_id, "OUTPUT_UPLOADING", progress=88) if task_id else None
        video_object = f"projects/{project_id}/output.mp4"
        video_url = get_storage_client().upload_file(video_path, video_object)

        db.commit()
        generation_task_service.finish_step_sync(db, step, progress=95, output_snapshot={"video_url": video_url}) if task_id else None
        logger.info(f"[瑙嗛] 瀹屾垚: {video_object}")

        # ---- Step 6: 鏇存柊椤圭洰鐘舵€?----
        project.video_output_url = video_url
        for frame in frames:
            frame.dirty = 0
        project_workflow_state.mark_project_completed(project, task_id)
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
        logger.info(f"[瀹屾垚] project_id={project_id}, 瑙嗛宸茬敓鎴? {video_object}")

    except SoftTimeLimitExceeded as exc:
        logger.error(f"[瑙嗛浠诲姟瓒呮椂] project_id={project_id}", exc_info=True)
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
        except Exception:
            logger.warning("[failure handler] failed to update video timeout state", exc_info=True)
        if will_retry:
            raise self.retry(exc=exc, countdown=_retry_countdown(self.request.retries))
        raise
    except Exception as exc:
        logger.error(f"[澶辫触] project_id={project_id}, error={exc}", exc_info=True)
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
        project = db.execute(select(Project).where(Project.id == project_id)).scalar_one()
        reference_images = extract_reference_images(project)
        frame.image_url = None
        frame.status = 0
        frames = image_generation_service.generate_frame_images(
            [frame],
            project_id,
            reference_images=reference_images,
        )
        db.commit()
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
        frame.dirty = 1
        generation_task_service.finish_step_sync(
            db, step, progress=100, output_snapshot={"image_url": frame.image_url}
        ) if task_id else None
        generation_task_service.update_task_sync(
            db, task_id, status="succeeded", progress=100, current_step="FRAME_IMAGE_GENERATED",
            current_frame_id=frame_id,
        ) if task_id else None
        db.commit()
    except SoftTimeLimitExceeded as exc:
        logger.error(f"[鍗曞抚鍥剧墖浠诲姟瓒呮椂] project_id={project_id}, frame_id={frame_id}", exc_info=True)
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
        logger.error(f"[鍗曞抚鍥剧墖浠诲姟澶辫触] project_id={project_id}, frame_id={frame_id}, error={exc}", exc_info=True)
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
        output_dir = os.path.join(temp_dir, f"project_{project_id}_frame_{frame_id}")
        video_path = video_composer.compose_frames(
            [frame],
            output_dir,
            allow_placeholder_segments=False,
        )
        object_key = f"projects/{project_id}/frames/frame_{frame_id}.mp4"
        video_url = get_storage_client().upload_file(video_path, object_key)
        # 单帧视频产物写入 video_url，避免覆盖帧配音/音效 URL。
        frame.video_url = video_url
        frame.dirty = 0
        project = db.execute(select(Project).where(Project.id == project_id)).scalar_one()
        project.dirty_stage = "video"
        db.commit()
        generation_task_service.finish_step_sync(
            db, step, progress=100, output_snapshot={"video_url": video_url}
        ) if task_id else None
        generation_task_service.update_task_sync(
            db, task_id, status="succeeded", progress=100, current_step="FRAME_VIDEO_GENERATED",
            current_frame_id=frame_id,
        ) if task_id else None
    except SoftTimeLimitExceeded as exc:
        logger.error(f"[鍗曞抚瑙嗛浠诲姟瓒呮椂] project_id={project_id}, frame_id={frame_id}", exc_info=True)
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
        logger.error(f"[鍗曞抚瑙嗛浠诲姟澶辫触] project_id={project_id}, frame_id={frame_id}, error={exc}", exc_info=True)
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
        import shutil
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


