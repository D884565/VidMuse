-- 为 projects 表添加工作流相关列（workflow_stage, stage_status, last_task_id, dirty_stage, 确认时间戳）
-- 这些列在 init.sql 的 CREATE TABLE 中已定义，但缺少增量迁移，导致已有数据库缺少这些列。
-- 执行前请备份数据库。

USE aigc_video; -- 请替换为实际数据库名称

SET @db_name = DATABASE();
SET @table_name = 'projects';

-- workflow_stage
SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = @db_name AND TABLE_NAME = @table_name AND COLUMN_NAME = 'workflow_stage'
);
IF @col_exists = 0 THEN
    ALTER TABLE projects ADD COLUMN workflow_stage VARCHAR(30) NOT NULL DEFAULT 'created' COMMENT '工作流阶段: created/script/images/video/completed';
END IF;

-- stage_status
SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = @db_name AND TABLE_NAME = @table_name AND COLUMN_NAME = 'stage_status'
);
IF @col_exists = 0 THEN
    ALTER TABLE projects ADD COLUMN stage_status VARCHAR(30) NOT NULL DEFAULT 'idle' COMMENT '阶段状态: idle/running/done/failed';
END IF;

-- last_task_id
SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = @db_name AND TABLE_NAME = @table_name AND COLUMN_NAME = 'last_task_id'
);
IF @col_exists = 0 THEN
    ALTER TABLE projects ADD COLUMN last_task_id VARCHAR(80) COMMENT '最近一次异步任务ID';
END IF;

-- dirty_stage
SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = @db_name AND TABLE_NAME = @table_name AND COLUMN_NAME = 'dirty_stage'
);
IF @col_exists = 0 THEN
    ALTER TABLE projects ADD COLUMN dirty_stage VARCHAR(30) COMMENT '脏数据阶段标记';
END IF;

-- script_confirmed_at
SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = @db_name AND TABLE_NAME = @table_name AND COLUMN_NAME = 'script_confirmed_at'
);
IF @col_exists = 0 THEN
    ALTER TABLE projects ADD COLUMN script_confirmed_at DATETIME COMMENT '剧本确认时间';
END IF;

-- images_confirmed_at
SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = @db_name AND TABLE_NAME = @table_name AND COLUMN_NAME = 'images_confirmed_at'
);
IF @col_exists = 0 THEN
    ALTER TABLE projects ADD COLUMN images_confirmed_at DATETIME COMMENT '图片确认时间';
END IF;

-- video_confirmed_at
SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = @db_name AND TABLE_NAME = @table_name AND COLUMN_NAME = 'video_confirmed_at'
);
IF @col_exists = 0 THEN
    ALTER TABLE projects ADD COLUMN video_confirmed_at DATETIME COMMENT '视频确认时间';
END IF;

-- music_config
SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = @db_name AND TABLE_NAME = @table_name AND COLUMN_NAME = 'music_config'
);
IF @col_exists = 0 THEN
    ALTER TABLE projects ADD COLUMN music_config JSON COMMENT '音乐配置，如当前 BGM ID';
END IF;

-- 修复 last_task_id 列类型：老数据库可能是 BIGINT，需要改为 VARCHAR(80) 以存储 gen_xxx 格式的任务ID
SET @col_type = (
    SELECT DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = @db_name AND TABLE_NAME = @table_name AND COLUMN_NAME = 'last_task_id'
);
IF @col_type = 'bigint' THEN
    ALTER TABLE projects MODIFY COLUMN last_task_id VARCHAR(80) COMMENT '最近一次异步任务ID';
END IF;

-- 修复 conversations.task_id：老数据库可能是 BIGINT，需要改为 VARCHAR(80)
SET @col_type = (
    SELECT DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = @db_name AND TABLE_NAME = 'conversations' AND COLUMN_NAME = 'task_id'
);
IF @col_type = 'bigint' THEN
    ALTER TABLE conversations MODIFY COLUMN task_id VARCHAR(80) COMMENT '关联任务 ID';
END IF;

-- 修复 generation_task_steps.task_id：老数据库可能是 BIGINT 且有错误的 FK
SET @col_type = (
    SELECT DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = @db_name AND TABLE_NAME = 'generation_task_steps' AND COLUMN_NAME = 'task_id'
);
IF @col_type = 'bigint' THEN
    -- 先删除可能存在的错误 FK 约束
    SET @fk_name = (
        SELECT CONSTRAINT_NAME FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = @db_name AND TABLE_NAME = 'generation_task_steps'
        AND COLUMN_NAME = 'task_id' AND REFERENCED_TABLE_NAME IS NOT NULL
    );
    IF @fk_name IS NOT NULL THEN
        SET @sql = CONCAT('ALTER TABLE generation_task_steps DROP FOREIGN KEY ', @fk_name);
        PREPARE stmt FROM @sql;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
    END IF;
    ALTER TABLE generation_task_steps MODIFY COLUMN task_id VARCHAR(80) NOT NULL COMMENT '任务ID';
END IF;

-- 修复 generation_tasks：老数据库可能缺少新版工作流追踪字段
SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = @db_name AND TABLE_NAME = 'generation_tasks' AND COLUMN_NAME = 'task_id'
);
IF @col_exists = 0 THEN
    ALTER TABLE generation_tasks
        ADD COLUMN task_id VARCHAR(80) NULL COMMENT '任务ID' AFTER id;
END IF;

SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = @db_name AND TABLE_NAME = 'generation_tasks' AND COLUMN_NAME = 'current_stage'
);
IF @col_exists = 0 THEN
    ALTER TABLE generation_tasks
        ADD COLUMN current_stage VARCHAR(50) NULL COMMENT '当前阶段' AFTER status;
END IF;

SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = @db_name AND TABLE_NAME = 'generation_tasks' AND COLUMN_NAME = 'max_retries'
);
IF @col_exists = 0 THEN
    ALTER TABLE generation_tasks
        ADD COLUMN max_retries INT DEFAULT 3 COMMENT '最大重试次数' AFTER retry_count;
END IF;

SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = @db_name AND TABLE_NAME = 'generation_tasks' AND COLUMN_NAME = 'trigger_source'
);
IF @col_exists = 0 THEN
    ALTER TABLE generation_tasks
        ADD COLUMN trigger_source VARCHAR(50) DEFAULT 'manual' COMMENT '触发来源' AFTER error_message;
END IF;

SET @status_type = (
    SELECT COLUMN_TYPE FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = @db_name AND TABLE_NAME = 'generation_tasks' AND COLUMN_NAME = 'status'
);
IF @status_type IS NOT NULL THEN
    ALTER TABLE generation_tasks MODIFY COLUMN status VARCHAR(30) NOT NULL DEFAULT 'queued' COMMENT '状态';
END IF;

SET @task_id_type = (
    SELECT DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = @db_name AND TABLE_NAME = 'generation_tasks' AND COLUMN_NAME = 'task_id'
);
IF @task_id_type IS NOT NULL THEN
    UPDATE generation_tasks
       SET task_id = CONCAT('legacy_', id)
     WHERE task_id IS NULL OR task_id = '';
    ALTER TABLE generation_tasks MODIFY COLUMN task_id VARCHAR(80) NOT NULL COMMENT '任务ID';
END IF;

SET @idx_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
    WHERE TABLE_SCHEMA = @db_name AND TABLE_NAME = 'generation_tasks' AND INDEX_NAME = 'idx_task_id'
);
IF @idx_exists = 0 THEN
    CREATE INDEX idx_task_id ON generation_tasks (task_id);
END IF;

SET @idx_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
    WHERE TABLE_SCHEMA = @db_name AND TABLE_NAME = 'generation_tasks' AND INDEX_NAME = 'uq_generation_tasks_task_id'
);
IF @idx_exists = 0 THEN
    ALTER TABLE generation_tasks ADD CONSTRAINT uq_generation_tasks_task_id UNIQUE (task_id);
END IF;

-- 创建可能缺失的 generation_frame_progress 表
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='帧级生成进度表';

SELECT 'projects 表工作流相关列迁移完成' AS result;
