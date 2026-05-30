"""Celery 视频生成异步任务（基于 frames 表）"""
import json
import os
import logging
import tempfile
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.v1.app.generate.temp.celery_app import celery_app
from backend.v1.app.config.config import settings
from backend.v1.app.models.project import Project
from backend.v1.app.models.frame import Frame
from backend.v1.app.models.asset import Asset
from backend.v1.app.generate.service.tts_service import tts_service
from backend.v1.app.generate.service.image_generation_service import image_generation_service
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

# Celery Worker 中使用同步数据库连接
_sync_engine = create_engine(settings.sync_db_url)


def _get_sync_db() -> Session:
    return Session(_sync_engine)


def _mark_project_failed(db: Session, project_id: int, stage: str) -> None:
    project = db.execute(select(Project).where(Project.id == project_id)).scalar_one_or_none()
    if project:
        project_workflow_state.mark_project_stage_failed(project, stage)
        db.commit()


@celery_app.task(bind=True, max_retries=3, name="generate_image_task")
def generate_image_task(self, project_id: int, task_id: int | None = None):
    """图片阶段后台任务：生成首帧图并写入图片审核卡片，不触发视频生成。"""
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
            raise ValueError(f"项目 {project_id} 没有帧数据，请先生成剧本")

        product_images = None
        if project.product_info:
            try:
                product_data = json.loads(project.product_info)
                main_images = product_data.get("main_images", [])
                if main_images:
                    product_images = {"商品主图": main_images}
            except (json.JSONDecodeError, TypeError):
                pass

        step = generation_task_service.start_step_sync(db, task_id, "IMAGE_GENERATING", progress=10) if task_id else None
        frames = image_generation_service.generate_frame_images(frames, project_id, product_images=product_images)
        db.commit()
        failed = [frame.id for frame in frames if frame.status == 3]
        if failed:
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
        logger.error(f"[图片任务失败] project_id={project_id}, error={exc}", exc_info=True)
        will_retry = self.request.retries < self.max_retries
        if db:
            db.rollback()
        fail_db = _get_sync_db()
        try:
            if task_id:
                generation_task_service.update_task_sync(
                    fail_db,
                    task_id,
                    status="queued" if will_retry else "failed",
                    progress=100 if not will_retry else None,
                    current_step="RETRYING" if will_retry else "IMAGE_GENERATION_FAILED",
                    error_code=None if will_retry else "IMAGE_GENERATION_FAILED",
                    error_message=str(exc),
                )
            if not will_retry:
                _mark_project_failed(fail_db, project_id, "image")
        finally:
            fail_db.close()
        if will_retry:
            raise self.retry(exc=exc)
        raise
    finally:
        if db:
            db.close()


@celery_app.task(bind=True, max_retries=3, name="generate_video_task")
def generate_video_task(self, project_id: int, task_id: int | None = None):
    """
    视频生成异步任务（基于 frames 表）。

    流程：
    Step 1: 从 frames 表读取所有帧
    Step 2: TTS 生成配音音频（拼接所有帧的文案）
    Step 3: 为每个帧生成图片（火山引擎 Seedream 5.0）
    Step 4: 为每个帧生成视频（Seedance 1.5，使用图片作为首帧）
    Step 5: 拼接所有视频片段
    Step 6: 上传到 TOS 并更新状态
    """
    logger.info(f"[任务启动] project_id={project_id}")
    temp_dir = tempfile.mkdtemp()
    db = None
    audio_path = None

    try:
        db = _get_sync_db()
        generation_task_service.start_task_sync(db, task_id, "PROJECT_VALIDATION") if task_id else None

        # ---- Step 1: 读取 frames ----
        step = generation_task_service.start_step_sync(db, task_id, "PROJECT_VALIDATION", progress=5) if task_id else None
        frames = list(db.execute(
            select(Frame)
            .where(Frame.project_id == project_id)
            .order_by(Frame.sequence)
        ).scalars())
        if not frames:
            raise ValueError(f"项目 {project_id} 没有帧数据，请先生成剧本")

        project = db.execute(select(Project).where(Project.id == project_id)).scalar_one()
        project_workflow_state.mark_project_stage_running(project, "video", task_id)
        project.status = "rendering"
        db.commit()
        generation_task_service.finish_step_sync(db, step, progress=10, output_snapshot={"frames_count": len(frames)}) if task_id else None
        generation_task_service.update_task_sync(db, task_id, progress=10, current_step="PROJECT_VALIDATION") if task_id else None
        logger.info(f"[读取帧] project_id={project_id}, frames={len(frames)}")

        # ---- Step 2: TTS ----
        step = generation_task_service.start_step_sync(db, task_id, "TTS_GENERATING", progress=10) if task_id else None
        logger.info("[TTS] 开始生成配音...")
        # 拼接所有帧的文案（从 ai_params 中取 text）
        texts = []
        for frame in frames:
            ai_params = frame.ai_params or {}
            text = ai_params.get("text", "") or frame.description or ""
            if text:
                texts.append(text)
        full_text = " ".join(texts)
        tts_voice = (frames[0].ai_params or {}).get("voice_style", "")
        # voice_style 映射到火山引擎 TTS 音色
        voice_map = {
            "excited": "zh_female_cancan_mars_bigtts",
            "confident": "zh_female_shuangkuai_moon_bigtts",
            "urgent": "zh_male_chunhou_mars_bigtts",
            "warm": "zh_female_tianmei_mars_bigtts",
            "professional": "zh_male_yangguang_mars_bigtts",
        }
        tts_voice = project.voice_type or voice_map.get(tts_voice, "zh_female_cancan_mars_bigtts")
        audio_path = tts_service.generate_audio(full_text, tts_voice)

        # 上传配音到 TOS，存入 project.audio_url
        audio_object = f"projects/{project_id}/audio.mp3"
        audio_url = get_storage_client().upload_file(audio_path, audio_object)
        project.audio_url = audio_url
        db.commit()
        generation_task_service.finish_step_sync(db, step, progress=25, output_snapshot={"audio_url": audio_url}) if task_id else None
        generation_task_service.update_task_sync(db, task_id, progress=25, current_step="TTS_GENERATING") if task_id else None
        logger.info(f"[TTS] 项目级配音完成: {audio_object}")

        # ---- Step 3: 为每个帧生成图片 ----
        step = generation_task_service.start_step_sync(db, task_id, "IMAGE_GENERATING", progress=30) if task_id else None
        logger.info("[图片] 开始生成帧配图...")
        # 解析商品图片，传给图片生成服务做参考图
        product_images = None
        if project.product_info:
            try:
                product_data = json.loads(project.product_info)
                main_images = product_data.get("main_images", [])
                if main_images:
                    product_images = {"商品主图": main_images}
                    logger.info(f"[图片] 已加载 {len(main_images)} 张商品主图作为参考")
            except (json.JSONDecodeError, TypeError):
                pass
        frames = image_generation_service.generate_frame_images(frames, project_id, product_images=product_images)
        db.commit()
        failed_images = [f.id for f in frames if f.status == 3]
        generation_task_service.finish_step_sync(db, step, status="failed" if failed_images else "succeeded", progress=45, output_snapshot={"failed_frame_ids": failed_images}, error_message="部分分镜图片生成失败" if failed_images else None) if task_id else None
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
        logger.info(f"[图片] 完成: {len(frames)}张")

        # ---- Step 4+5: 为每个帧生成视频并拼接 ----
        step = generation_task_service.start_step_sync(db, task_id, "VIDEO_GENERATING", progress=50) if task_id else None
        logger.info("[视频] 开始生成帧视频...")
        output_dir = os.path.join(temp_dir, f"project_{project_id}")
        video_path = video_composer.compose_frames(frames, output_dir)
        db.commit()
        failed_videos = [f.id for f in frames if f.status == 3]
        generation_task_service.finish_step_sync(db, step, status="failed" if failed_videos else "succeeded", progress=75, output_snapshot={"failed_frame_ids": failed_videos}, error_message="部分分镜视频生成失败" if failed_videos else None) if task_id else None
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

        # ---- Step 5.5: 合并 TTS 音频到视频 ----
        step = generation_task_service.start_step_sync(db, task_id, "AUDIO_MIXING", progress=78) if task_id else None
        if audio_path and os.path.exists(audio_path):
            try:
                merged_path = os.path.join(output_dir, "merged_output.mp4")
                ffmpeg_utils.replace_audio(video_path, audio_path, merged_path)
                video_path = merged_path
                logger.info("[音频合并] TTS 配音已合并到视频")
                generation_task_service.finish_step_sync(db, step, progress=85, output_snapshot={"merged": True}) if task_id else None
            except Exception as e:
                logger.warning(f"[音频合并] 合并失败，降级上传无声视频: {e}")
                generation_task_service.finish_step_sync(db, step, status="failed", progress=85, error_message=str(e)) if task_id else None
        else:
            logger.warning("[音频合并] 无 TTS 音频文件，跳过合并")
            generation_task_service.finish_step_sync(db, step, status="skipped", progress=85, error_message="no audio file") if task_id else None

        # ---- Step 5.6: 生成 BGM 并混入视频（暂时禁用，接口保留） ----
        # bgm_desc = (frames[0].ai_params or {}).get("bgm", "")
        # if bgm_desc:
        #     bgm_path = music_generation_service.generate_bgm(bgm_desc)
        #     if bgm_path and os.path.exists(bgm_path):
        #         try:
        #             bgm_output = os.path.join(output_dir, "bgm_output.mp4")
        #             ffmpeg_utils.add_bgm(video_path, bgm_path, bgm_output, bgm_volume=0.3, original_volume=1.0)
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
        #         logger.warning("[BGM] BGM 生成失败，跳过混音")
        # else:
        #     logger.info("[BGM] 无 BGM 描述，跳过生成")

        # 上传成品视频到 TOS
        step = generation_task_service.start_step_sync(db, task_id, "OUTPUT_UPLOADING", progress=88) if task_id else None
        video_object = f"projects/{project_id}/output.mp4"
        video_url = get_storage_client().upload_file(video_path, video_object)

        # 记录资产
        db.add(Asset(
            user_id=project.user_id,
            type=2,  # 视频
            title="成品视频",
            url=video_url,
            duration=int(sum(float(frame.duration or 0) for frame in frames)),
            format="mp4",
            source_type=1,  # AI生成
        ))
        db.commit()
        generation_task_service.finish_step_sync(db, step, progress=95, output_snapshot={"video_url": video_url}) if task_id else None
        logger.info(f"[视频] 完成: {video_object}")

        # ---- Step 6: 更新项目状态 ----
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
        logger.info(f"[完成] project_id={project_id}, 视频已生成: {video_object}")

    except Exception as exc:
        logger.error(f"[失败] project_id={project_id}, error={exc}", exc_info=True)
        will_retry = self.request.retries < self.max_retries
        fail_db = None
        try:
            if db:
                db.rollback()
            fail_db = _get_sync_db()
            if task_id:
                task = generation_task_service.get_task_sync(fail_db, task_id)
                if task:
                    task.retry_count = self.request.retries + 1
                    task.error_message = str(exc)
                    task.current_step = "RETRYING" if will_retry else "FAILED"
                    if will_retry:
                        task.status = "queued"
                    else:
                        task.status = "failed"
                        task.progress = 100
                        task.error_code = "VIDEO_GENERATION_FAILED"
                    fail_db.commit()
            if not will_retry:
                project = fail_db.execute(select(Project).where(Project.id == project_id)).scalar_one()
                project_workflow_state.mark_project_stage_failed(project, "video", task_id)
                fail_db.commit()
        except Exception:
            logger.warning("[失败处理] 更新任务失败状态失败", exc_info=True)
        finally:
            if fail_db:
                fail_db.close()
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
        # 清理临时文件
        import shutil
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


@celery_app.task(bind=True, max_retries=3, name="generate_frame_image_task")
def generate_frame_image_task(self, project_id: int, frame_id: int, task_id: int | None = None):
    """单分镜图片重生成任务，只更新指定分镜图片，不自动合成整片。"""
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
        frame.image_url = None
        frame.status = 0
        frames = image_generation_service.generate_frame_images([frame], project_id)
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
        if db:
            db.rollback()
        if task_id:
            fail_db = _get_sync_db()
            try:
                generation_task_service.update_task_sync(
                    fail_db, task_id, status="failed", progress=100,
                    current_step="FRAME_IMAGE_FAILED", error_code="FRAME_IMAGE_FAILED",
                    error_message=str(exc),
                )
            finally:
                fail_db.close()
        raise
    finally:
        if db:
            db.close()


@celery_app.task(bind=True, max_retries=3, name="generate_frame_video_task")
def generate_frame_video_task(self, project_id: int, frame_id: int, task_id: int | None = None):
    """单分镜视频重生成任务，只生成指定分镜片段并记录任务结果。"""
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
        if db:
            db.rollback()
        if task_id:
            fail_db = _get_sync_db()
            try:
                generation_task_service.update_task_sync(
                    fail_db, task_id, status="failed", progress=100,
                    current_step="FRAME_VIDEO_FAILED", error_code="FRAME_VIDEO_FAILED",
                    error_message=str(exc),
                )
            finally:
                fail_db.close()
        raise
    finally:
        if db:
            db.close()
        import shutil
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


@celery_app.task(bind=True, max_retries=2, name="export_video_task")
def export_video_task(self, project_id: int, task_id: int | None = None, aspect_ratio: str = "9:16"):
    """导出最终视频。第一版复用已生成视频文件并记录导出资产，后续可扩展转码参数。"""
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
            title=f"导出视频 {aspect_ratio}",
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
        if db:
            db.rollback()
        if task_id:
            fail_db = _get_sync_db()
            try:
                generation_task_service.update_task_sync(
                    fail_db, task_id, status="failed", progress=100,
                    current_step="EXPORT_FAILED", error_code="EXPORT_FAILED",
                    error_message=str(exc),
                )
            finally:
                fail_db.close()
        raise
    finally:
        if db:
            db.close()
