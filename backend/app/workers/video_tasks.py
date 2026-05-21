"""Celery 视频生成异步任务"""
import os
import json
import logging
import tempfile
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.app.core.celery_app import celery_app
from backend.app.core.config import settings
from backend.app.models.project import Project
from backend.app.models.script import Script
from backend.app.models.material import Material
from backend.app.services.tts_service import tts_service
from backend.app.services.image_service import image_service
from backend.app.services.video_composer import video_composer
from backend.app.services.minio_service import minio_service

logger = logging.getLogger(__name__)

# Celery Worker 中使用同步数据库连接
_sync_engine = create_engine(settings.sync_db_url)


def _get_sync_db() -> Session:
    return Session(_sync_engine)


@celery_app.task(bind=True, max_retries=3, name="generate_video_task")
def generate_video_task(self, project_id: int, script_id: int):
    """
    视频生成异步任务。

    由 LangGraph 编排（当前为顺序执行），各步骤：
    Step 1: TTS 生成配音音频
    Step 2: 准备场景配图
    Step 3: 合成视频
    Step 4: 上传 MinIO 并更新状态
    """
    logger.info(f"[任务启动] project_id={project_id}, script_id={script_id}")
    temp_dir = tempfile.mkdtemp()

    try:
        db = _get_sync_db()

        # 读取剧本
        script = db.execute(select(Script).where(Script.id == script_id)).scalar_one()
        script_content = json.loads(script.content)
        logger.info(f"[读取剧本] project_id={project_id}, scenes={len(script_content.get('body', []))}")

        # ---- Step 1: TTS ----
        logger.info("[TTS] 开始生成配音...")
        audio_path = tts_service.generate_audio(script_content["full_text"])
        # 上传配音到 MinIO
        audio_object = f"projects/{project_id}/audio_{script_id}.mp3"
        minio_service.upload_file(audio_path, audio_object)
        # 记录素材
        db.add(Material(
            project_id=project_id, script_id=script_id,
            type=3, title="配音音频", url=audio_object,
            format="mp3", source_type=1,
        ))
        db.commit()
        logger.info(f"[TTS] 完成: {audio_object}")

        # ---- Step 2: 配图 ----
        logger.info("[图片] 开始准备场景配图...")
        image_paths = image_service.prepare_scene_images(script_content)
        image_objects = []
        for i, img_path in enumerate(image_paths):
            img_object = f"projects/{project_id}/scene_{i + 1}.png"
            minio_service.upload_file(img_path, img_object)
            image_objects.append(img_object)
            db.add(Material(
                project_id=project_id, script_id=script_id,
                type=1, title=f"场景{i+1}配图", url=img_object,
                format="png", source_type=1, scene_index=i + 1,
            ))
        db.commit()
        logger.info(f"[图片] 完成: {len(image_objects)}张")

        # ---- Step 3: 合成视频 ----
        logger.info("[合成] 开始合成视频...")
        output_dir = os.path.join(temp_dir, f"project_{project_id}")
        video_path = video_composer.compose(
            audio_path=audio_path,
            images=image_paths,
            subtitles=script_content.get("body", []),
            output_dir=output_dir,
        )
        # 上传成品视频到 MinIO
        video_object = f"projects/{project_id}/output.mp4"
        minio_service.upload_file(video_path, video_object)

        # 记录素材
        db.add(Material(
            project_id=project_id, script_id=script_id,
            type=5, title="成品视频", url=video_object,
            format="mp4", source_type=1,
        ))
        db.commit()
        logger.info(f"[合成] 完成: {video_object}")

        # ---- Step 4: 更新项目状态 ----
        project = db.execute(select(Project).where(Project.id == project_id)).scalar_one()
        project.video_output_url = video_object
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
