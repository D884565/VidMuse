-- generation_tracker_tables.sql
-- 生成任务追踪表

-- 生成任务表（阶段级）
CREATE TABLE IF NOT EXISTS generation_tasks (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    task_id VARCHAR(80) NOT NULL UNIQUE COMMENT '任务ID (gen_xxxxx)',
    project_id BIGINT NOT NULL COMMENT '关联项目ID',
    task_type VARCHAR(50) NOT NULL COMMENT '任务类型: render, image_retry, video_retry, frame_image, frame_video',
    status VARCHAR(30) NOT NULL DEFAULT 'queued' COMMENT '状态: queued, running, succeeded, failed, cancelled',
    current_stage VARCHAR(50) COMMENT '当前阶段: tts, image, video, audio_mix, bgm_mix, output',
    progress INT DEFAULT 0 COMMENT '整体进度 0-100',
    retry_count INT DEFAULT 0 COMMENT '重试次数',
    max_retries INT DEFAULT 3 COMMENT '最大重试次数',
    error_code VARCHAR(100) COMMENT '错误码',
    error_message TEXT COMMENT '错误信息',
    trigger_source VARCHAR(50) DEFAULT 'manual' COMMENT '触发来源: manual, resume, user_revision',
    celery_task_id VARCHAR(255) COMMENT 'Celery任务ID',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    started_at DATETIME COMMENT '开始时间',
    finished_at DATETIME COMMENT '完成时间',

    INDEX idx_project_id (project_id),
    INDEX idx_status (status),
    INDEX idx_task_id (task_id)
) COMMENT '生成任务表';

-- 帧级生成进度表
CREATE TABLE IF NOT EXISTS generation_frame_progress (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    task_id VARCHAR(80) NOT NULL COMMENT '关联任务ID',
    project_id BIGINT NOT NULL COMMENT '关联项目ID',
    frame_id BIGINT NOT NULL COMMENT '帧ID',
    stage VARCHAR(50) NOT NULL COMMENT '阶段: image, video',
    status VARCHAR(30) NOT NULL DEFAULT 'pending' COMMENT '状态: pending, running, succeeded, failed',
    attempt_count INT DEFAULT 0 COMMENT '尝试次数',
    error_message TEXT COMMENT '错误信息',
    result_url VARCHAR(500) COMMENT '生成结果URL',
    started_at DATETIME COMMENT '开始时间',
    finished_at DATETIME COMMENT '完成时间',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uk_task_frame_stage (task_id, frame_id, stage),
    INDEX idx_task_id (task_id),
    INDEX idx_project_stage (project_id, stage),
    INDEX idx_status (status)
) COMMENT '帧级生成进度表';
