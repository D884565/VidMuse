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

SELECT 'projects 表工作流相关列迁移完成' AS result;
