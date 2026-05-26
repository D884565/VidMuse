"""Celery 视频生成异步任务（基于 frames 表）"""
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
from backend.store.obj.factory import get_storage_client

logger = logging.getLogger(__name__)

# Celery Worker 中使用同步数据库连接
_sync_engine = create_engine(settings.sync_db_url)


def _get_sync_db() -> Session:
    return Session(_sync_engine)


@celery_app.task(bind=True, max_retries=3, name="generate_video_task")
def generate_video_task(self, project_id: int):
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

    try:
        db = _get_sync_db()

        # ---- Step 1: 读取 frames ----
        frames = list(db.execute(
            select(Frame)
            .where(Frame.project_id == project_id)
            .order_by(Frame.sequence)
        ).scalars())
        if not frames:
            raise ValueError(f"项目 {project_id} 没有帧数据，请先生成剧本")

        project = db.execute(select(Project).where(Project.id == project_id)).scalar_one()
        logger.info(f"[读取帧] project_id={project_id}, frames={len(frames)}")

        # ---- Step 2: TTS ----
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
        # voice_style 是 excited/confident 等风格，映射到 TTS 音色
        voice_map = {
            "excited": "zh_female_cancan_mars_bigtts",
            "confident": "zh_female_cancan_mars_bigtts",
            "urgent": "zh_female_cancan_mars_bigtts",
            "warm": "zh_female_cancan_mars_bigtts",
            "professional": "zh_female_cancan_mars_bigtts",
        }
        tts_voice = voice_map.get(tts_voice, "zh_female_cancan_mars_bigtts")
        audio_path = tts_service.generate_audio(full_text, tts_voice)

        # 上传配音到 TOS，存入 project.audio_url
        audio_object = f"projects/{project_id}/audio.mp3"
        audio_url = get_storage_client().upload_file(audio_path, audio_object)
        project.audio_url = audio_url
        db.commit()
        logger.info(f"[TTS] 完成: {audio_object}")

        # ---- Step 3: 为每个帧生成图片 ----
        logger.info("[图片] 开始生成帧配图...")
        frames = image_generation_service.generate_frame_images(frames, project_id)
        db.commit()
        logger.info(f"[图片] 完成: {len(frames)}张")

        # ---- Step 4+5: 为每个帧生成视频并拼接 ----
        logger.info("[视频] 开始生成帧视频...")
        output_dir = os.path.join(temp_dir, f"project_{project_id}")
        video_path = video_composer.compose_frames(frames, output_dir)

        # ---- Step 5.5: 合并 TTS 音频到视频 ----
        if audio_path and os.path.exists(audio_path):
            try:
                merged_path = os.path.join(output_dir, "merged_output.mp4")
                ffmpeg_utils.replace_audio(video_path, audio_path, merged_path)
                video_path = merged_path
                logger.info("[音频合并] TTS 配音已合并到视频")
            except Exception as e:
                logger.warning(f"[音频合并] 合并失败，降级上传无声视频: {e}")
        else:
            logger.warning("[音频合并] 无 TTS 音频文件，跳过合并")

        # ---- Step 5.6: 生成 BGM 并混入视频 ----
        bgm_desc = (frames[0].ai_params or {}).get("bgm", "")
        if bgm_desc:
            bgm_path = music_generation_service.generate_bgm(bgm_desc)
            if bgm_path and os.path.exists(bgm_path):
                try:
                    bgm_output = os.path.join(output_dir, "bgm_output.mp4")
                    ffmpeg_utils.add_bgm(video_path, bgm_path, bgm_output, bgm_volume=0.3, original_volume=1.0)
                    video_path = bgm_output
                    logger.info("[BGM] 背景音乐已混入视频")
                except Exception as e:
                    logger.warning(f"[BGM] 混音失败，降级上传无 BGM 视频: {e}")
                finally:
                    # 清理 BGM 临时文件
                    try:
                        os.remove(bgm_path)
                    except OSError:
                        pass
            else:
                logger.warning("[BGM] BGM 生成失败，跳过混音")
        else:
            logger.info("[BGM] 无 BGM 描述，跳过生成")

        # 上传成品视频到 TOS
        video_object = f"projects/{project_id}/output.mp4"
        video_url = get_storage_client().upload_file(video_path, video_object)

        # 记录资产
        db.add(Asset(
            user_id=project.user_id,
            type=2,  # 视频
            title="成品视频",
            url=video_url,
            format="mp4",
            source_type=1,  # AI生成
        ))
        db.commit()
        logger.info(f"[视频] 完成: {video_object}")

        # ---- Step 6: 更新项目状态 ----
        project.video_output_url = video_url
        project.status = "completed"
        db.commit()
        logger.info(f"[完成] project_id={project_id}, 视频已生成: {video_object}")

    except Exception as exc:
        logger.error(f"[失败] project_id={project_id}, error={exc}", exc_info=True)
        # 更新项目状态为失败
        try:
            db = _get_sync_db()
            project = db.execute(select(Project).where(Project.id == project_id)).scalar_one()
            project.status = "failed"
            db.commit()
        except Exception:
            pass
        # 重试
        raise self.retry(exc=exc)

    finally:
        # 清理临时文件
        import shutil
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
