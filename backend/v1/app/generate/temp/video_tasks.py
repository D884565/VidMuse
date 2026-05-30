"""Celery video generation tasks based on frames."""
import os
import logging
import tempfile
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.v1.app.generate.temp.celery_app import celery_app
from backend.store.database.sync_database import SessionLocal
from backend.v1.app.models.project import Project
from backend.v1.app.models.frame import Frame
from backend.v1.app.models.asset import Asset
from backend.v1.app.generate.service.tts_service import tts_service
from backend.v1.app.generate.service.image_generation_service import image_generation_service
from backend.v1.app.generate.service.reference_image_utils import extract_reference_images
from backend.v1.app.generate.service.video_composer import video_composer
from backend.v1.app.video.service.ffmpeg_utils import ffmpeg_utils
from backend.v1.app.generate.service.music_generation_service import music_generation_service
from backend.v1.app.generate.service.task_service import generation_task_service
from backend.v1.app.generate.service.workflow_blocks import build_video_stage_blocks
from backend.v1.app.generate.service.image_workflow import build_image_stage_message
from backend.v1.app.generate.service import project_workflow_state
from backend.v1.app.models.conversation import Conversation
from backend.store.obj.factory import get_storage_client

logger = logging.getLogger(__name__)

# Celery Worker 涓娇鐢ㄥ悓姝ユ暟鎹簱杩炴帴
def _get_sync_db() -> Session:
    return SessionLocal()


def _mark_project_failed(db: Session, project_id: int, stage: str) -> None:
    project = db.execute(select(Project).where(Project.id == project_id)).scalar_one_or_none()
    if project:
        project_workflow_state.mark_project_stage_failed(project, stage)
        db.commit()


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
    finally:
        fail_db.close()


@celery_app.task(bind=True, max_retries=3, name="generate_image_task")
def generate_image_task(self, project_id: int, task_id: int | None = None):
    """Generate frame images for the image workflow stage."""
    db = None
    try:
        db = _get_sync_db()
        generation_task_service.start_task_sync(db, task_id, "IMAGE_GENERATING") if task_id else None
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
            _mark_project_failed(db, project_id, "image")
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
    except Exception as exc:
        logger.error(f"[鍥剧墖浠诲姟澶辫触] project_id={project_id}, error={exc}", exc_info=True)
        # 让瞬时错误先走 Celery 重试，重试耗尽后再落最终失败状态。
        will_retry = self.request.retries < self.max_retries
        if db:
            db.rollback()
        _update_task_failure_state(
            task_id=task_id,
            project_id=project_id,
            stage="image",
            current_step="IMAGE_GENERATION_FAILED",
            error_code="IMAGE_GENERATION_FAILED",
            error_message=str(exc),
            will_retry=will_retry,
        )
        if will_retry:
            raise self.retry(exc=exc)
        raise
    finally:
        if db:
            db.close()


@celery_app.task(bind=True, max_retries=3, name="generate_video_task")
def generate_video_task(self, project_id: int, task_id: int | None = None):
    """Generate a full project video from frame images, narration, and composition."""
    logger.info(f"[浠诲姟鍚姩] project_id={project_id}")
    temp_dir = tempfile.mkdtemp()
    db = None
    audio_path = None

    try:
        db = _get_sync_db()
        generation_task_service.start_task_sync(db, task_id, "PROJECT_VALIDATION") if task_id else None

        # ---- Step 1: 璇诲彇 frames ----
        step = generation_task_service.start_step_sync(db, task_id, "PROJECT_VALIDATION", progress=5) if task_id else None
        frames = list(db.execute(
            select(Frame)
            .where(Frame.project_id == project_id)
            .order_by(Frame.sequence)
        ).scalars())
        if not frames:
            raise ValueError(f"椤圭洰 {project_id} 娌℃湁甯ф暟鎹紝璇峰厛鐢熸垚鍓ф湰")

        project = db.execute(select(Project).where(Project.id == project_id)).scalar_one()
        project_workflow_state.mark_project_stage_running(project, "video", task_id)
        project.status = "rendering"
        db.commit()
        generation_task_service.finish_step_sync(db, step, progress=10, output_snapshot={"frames_count": len(frames)}) if task_id else None
        generation_task_service.update_task_sync(db, task_id, progress=10, current_step="PROJECT_VALIDATION") if task_id else None
        logger.info(f"[璇诲彇甯 project_id={project_id}, frames={len(frames)}")

        # ---- Step 2: TTS ----
        step = generation_task_service.start_step_sync(db, task_id, "TTS_GENERATING", progress=10) if task_id else None
        logger.info("[TTS] 寮€濮嬬敓鎴愰厤闊?..")
        # 鎷兼帴鎵€鏈夊抚鐨勬枃妗堬紙浠?ai_params 涓彇 text锛?        texts = []
        for frame in frames:
            ai_params = frame.ai_params or {}
            text = ai_params.get("text", "") or frame.description or ""
            if text:
                texts.append(text)
        full_text = " ".join(texts)
        tts_voice = (frames[0].ai_params or {}).get("voice_style", "")
        # voice_style 鏄犲皠鍒扮伀灞卞紩鎿?TTS 闊宠壊
        voice_map = {
            "excited": "zh_female_cancan_mars_bigtts",
            "confident": "zh_female_shuangkuai_moon_bigtts",
            "urgent": "zh_male_chunhou_mars_bigtts",
            "warm": "zh_female_tianmei_mars_bigtts",
            "professional": "zh_male_yangguang_mars_bigtts",
        }
        tts_voice = project.voice_type or voice_map.get(tts_voice, "zh_female_cancan_mars_bigtts")
        audio_path = tts_service.generate_audio(full_text, tts_voice)

        # 涓婁紶閰嶉煶鍒?TOS锛屽瓨鍏?project.audio_url
        audio_object = f"projects/{project_id}/audio.mp3"
        audio_url = get_storage_client().upload_file(audio_path, audio_object)
        project.audio_url = audio_url
        db.commit()
        generation_task_service.finish_step_sync(db, step, progress=25, output_snapshot={"audio_url": audio_url}) if task_id else None
        generation_task_service.update_task_sync(db, task_id, progress=25, current_step="TTS_GENERATING") if task_id else None
        logger.info(f"[TTS] 椤圭洰绾ч厤闊冲畬鎴? {audio_object}")

        # ---- Step 3: 涓烘瘡涓抚鐢熸垚鍥剧墖 ----
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
            generation_task_service.update_task_sync(
                db,
                task_id,
                status="failed",
                progress=100,
                current_step="IMAGE_GENERATION_FAILED",
                error_code="IMAGE_GENERATION_FAILED",
                error_message=f"failed frame ids: {failed_images}",
            ) if task_id else None
            _mark_project_failed(db, project_id, "image")
            raise RuntimeError(f"IMAGE_GENERATION_FAILED: failed frame ids {failed_images}")
        logger.info(f"[image] completed frames: {len(frames)}")

        # ---- Step 4+5: 涓烘瘡涓抚鐢熸垚瑙嗛骞舵嫾鎺?----
        step = generation_task_service.start_step_sync(db, task_id, "VIDEO_GENERATING", progress=50) if task_id else None
        logger.info("[瑙嗛] 寮€濮嬬敓鎴愬抚瑙嗛...")
        output_dir = os.path.join(temp_dir, f"project_{project_id}")
        video_path = video_composer.compose_frames(frames, output_dir)
        db.commit()
        failed_videos = [f.id for f in frames if f.status == 3]
        generation_task_service.finish_step_sync(db, step, status="failed" if failed_videos else "succeeded", progress=75, output_snapshot={"failed_frame_ids": failed_videos}, error_message="閮ㄥ垎鍒嗛暅瑙嗛鐢熸垚澶辫触" if failed_videos else None) if task_id else None
        generation_task_service.update_task_sync(db, task_id, progress=75, current_step="VIDEO_GENERATING") if task_id else None
        if failed_videos:
            generation_task_service.update_task_sync(
                db,
                task_id,
                status="failed",
                progress=100,
                current_step="VIDEO_SEGMENT_GENERATION_FAILED",
                error_code="VIDEO_SEGMENT_GENERATION_FAILED",
                error_message=f"failed frame ids: {failed_videos}",
            ) if task_id else None
            _mark_project_failed(db, project_id, "video")
            raise RuntimeError(f"VIDEO_SEGMENT_GENERATION_FAILED: failed frame ids {failed_videos}")

        # ---- Step 5.5: 鍚堝苟 TTS 闊抽鍒拌棰?----
        step = generation_task_service.start_step_sync(db, task_id, "AUDIO_MIXING", progress=78) if task_id else None
        if audio_path and os.path.exists(audio_path):
            try:
                merged_path = os.path.join(output_dir, "merged_output.mp4")
                ffmpeg_utils.replace_audio(video_path, audio_path, merged_path)
                video_path = merged_path
                logger.info("[闊抽鍚堝苟] TTS 閰嶉煶宸插悎骞跺埌瑙嗛")
                generation_task_service.finish_step_sync(db, step, progress=85, output_snapshot={"merged": True}) if task_id else None
            except Exception as e:
                logger.warning(f"[闊抽鍚堝苟] 鍚堝苟澶辫触锛岄檷绾т笂浼犳棤澹拌棰? {e}")
                generation_task_service.finish_step_sync(db, step, status="failed", progress=85, error_message=str(e)) if task_id else None
        else:
            logger.warning("[audio] no TTS audio file, skip merging")
            generation_task_service.finish_step_sync(db, step, status="skipped", progress=85, error_message="no audio file") if task_id else None

        # ---- Step 5.6: 鐢熸垚 BGM 骞舵贩鍏ヨ棰戯紙鏆傛椂绂佺敤锛屾帴鍙ｄ繚鐣欙級 ----
        # bgm_desc = (frames[0].ai_params or {}).get("bgm", "")
        # if bgm_desc:
        #     bgm_path = music_generation_service.generate_bgm(bgm_desc)
        #     if bgm_path and os.path.exists(bgm_path):
        #         try:
        #             bgm_output = os.path.join(output_dir, "bgm_output.mp4")
        #             ffmpeg_utils.add_bgm(video_path, bgm_path, bgm_output, bgm_volume=0.3, original_volume=1.0)
        #             video_path = bgm_output
        #             logger.info("[BGM] 鑳屾櫙闊充箰宸叉贩鍏ヨ棰?)
        #         except Exception as e:
        #             logger.warning(f"[BGM] 娣烽煶澶辫触锛岄檷绾т笂浼犳棤 BGM 瑙嗛: {e}")
        #         finally:
        #             try:
        #                 os.remove(bgm_path)
        #             except OSError:
        #                 pass
        #     else:
        #         logger.warning("[BGM] BGM 鐢熸垚澶辫触锛岃烦杩囨贩闊?)
        # else:
        #     logger.info("[BGM] 鏃?BGM 鎻忚堪锛岃烦杩囩敓鎴?)

        # 涓婁紶鎴愬搧瑙嗛鍒?TOS
        step = generation_task_service.start_step_sync(db, task_id, "OUTPUT_UPLOADING", progress=88) if task_id else None
        video_object = f"projects/{project_id}/output.mp4"
        video_url = get_storage_client().upload_file(video_path, video_object)

        # 璁板綍璧勪骇
        db.add(Asset(
            user_id=project.user_id,
            type=2,  # 瑙嗛
            title="鎴愬搧瑙嗛",
            url=video_url,
            duration=int(sum(float(frame.duration or 0) for frame in frames)),
            format="mp4",
            source_type=1,  # AI鐢熸垚
        ))
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
                stage="video",
                current_step="FAILED",
                error_code="VIDEO_GENERATION_FAILED",
                error_message=str(exc),
                will_retry=will_retry,
            )
        except Exception:
            logger.warning("[failure handler] failed to update task state", exc_info=True)
        if will_retry:
            raise self.retry(exc=exc)
        raise exc

    finally:
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except OSError:
                pass
        if db:
            db.close()
        # 濞撳懐鎮婃稉瀛樻閺傚洣娆?        import shutil
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


@celery_app.task(bind=True, max_retries=3, name="generate_frame_image_task")
def generate_frame_image_task(self, project_id: int, frame_id: int, task_id: int | None = None):
    """Regenerate one frame image without composing the full video."""
    db = None
    try:
        db = _get_sync_db()
        generation_task_service.start_task_sync(db, task_id, "FRAME_IMAGE_GENERATING") if task_id else None
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
    except Exception as exc:
        will_retry = self.request.retries < self.max_retries
        if db:
            db.rollback()
        _update_task_failure_state(
            task_id=task_id,
            project_id=project_id,
            stage=None,
            current_step="FRAME_IMAGE_FAILED",
            error_code="FRAME_IMAGE_FAILED",
            error_message=str(exc),
            will_retry=will_retry,
        )
        if will_retry:
            raise self.retry(exc=exc)
        raise
    finally:
        if db:
            db.close()


@celery_app.task(bind=True, max_retries=3, name="generate_frame_video_task")
def generate_frame_video_task(self, project_id: int, frame_id: int, task_id: int | None = None):
    """Regenerate one frame video segment and record task output."""
    temp_dir = tempfile.mkdtemp()
    db = None
    try:
        db = _get_sync_db()
        generation_task_service.start_task_sync(db, task_id, "FRAME_VIDEO_GENERATING") if task_id else None
        step = generation_task_service.start_step_sync(
            db, task_id, "FRAME_VIDEO_GENERATING", progress=10, frame_id=frame_id
        ) if task_id else None
        frame = db.execute(
            select(Frame).where(Frame.id == frame_id, Frame.project_id == project_id)
        ).scalar_one()
        output_dir = os.path.join(temp_dir, f"project_{project_id}_frame_{frame_id}")
        video_path = video_composer.compose_frames([frame], output_dir)
        object_key = f"projects/{project_id}/frames/frame_{frame_id}.mp4"
        video_url = get_storage_client().upload_file(video_path, object_key)
        frame.audio_url = video_url
        frame.dirty = 1
        db.commit()
        generation_task_service.finish_step_sync(
            db, step, progress=100, output_snapshot={"video_url": video_url}
        ) if task_id else None
        generation_task_service.update_task_sync(
            db, task_id, status="succeeded", progress=100, current_step="FRAME_VIDEO_GENERATED",
            current_frame_id=frame_id,
        ) if task_id else None
    except Exception as exc:
        will_retry = self.request.retries < self.max_retries
        if db:
            db.rollback()
        _update_task_failure_state(
            task_id=task_id,
            project_id=project_id,
            stage=None,
            current_step="FRAME_VIDEO_FAILED",
            error_code="FRAME_VIDEO_FAILED",
            error_message=str(exc),
            will_retry=will_retry,
        )
        if will_retry:
            raise self.retry(exc=exc)
        raise
    finally:
        if db:
            db.close()
        import shutil
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


@celery_app.task(bind=True, max_retries=2, name="export_video_task")
def export_video_task(self, project_id: int, task_id: int | None = None, aspect_ratio: str = "9:16"):
    """Export the generated project video as an asset record."""
    db = None
    try:
        db = _get_sync_db()
        generation_task_service.start_task_sync(db, task_id, "EXPORTING") if task_id else None
        step = generation_task_service.start_step_sync(
            db, task_id, "EXPORTING", progress=10, input_snapshot={"aspect_ratio": aspect_ratio}
        ) if task_id else None
        project = db.execute(select(Project).where(Project.id == project_id)).scalar_one()
        if not project.video_output_url:
            raise ValueError("project has no generated video to export")
        asset = Asset(
            user_id=project.user_id,
            type=2,
            title=f"瀵煎嚭瑙嗛 {aspect_ratio}",
            url=project.video_output_url,
            duration=None,
            format="mp4",
            source_type=1,
            scope="output",
            metadata_={"aspect_ratio": aspect_ratio, "project_id": project_id},
        )
        db.add(asset)
        db.commit()
        generation_task_service.finish_step_sync(
            db, step, progress=100, output_snapshot={"video_url": project.video_output_url}
        ) if task_id else None
        generation_task_service.update_task_sync(
            db, task_id, status="succeeded", progress=100, current_step="EXPORTED"
        ) if task_id else None
    except Exception as exc:
        will_retry = self.request.retries < self.max_retries
        if db:
            db.rollback()
        _update_task_failure_state(
            task_id=task_id,
            project_id=project_id,
            stage=None,
            current_step="EXPORT_FAILED",
            error_code="EXPORT_FAILED",
            error_message=str(exc),
            will_retry=will_retry,
        )
        if will_retry:
            raise self.retry(exc=exc)
        raise
    finally:
        if db:
            db.close()
