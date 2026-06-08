-- 为 frames 表添加 version 列（帧版本号，用于乐观锁）
-- 执行前请备份数据库。

USE aigc_video; -- 请替换为实际数据库名称

SET @db_name = DATABASE();
SET @table_name = 'frames';

-- version
SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = @db_name AND TABLE_NAME = @table_name AND COLUMN_NAME = 'version'
);
IF @col_exists = 0 THEN
    ALTER TABLE frames ADD COLUMN version INT NOT NULL DEFAULT 1 COMMENT '帧版本号，每次修改+1，Celery任务完成时校验';
END IF;

SELECT 'frames 表 version 列迁移完成' AS result;
