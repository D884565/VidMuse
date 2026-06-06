-- 为projects表添加summary字段迁移脚本
-- 执行前请备份数据库

USE aigc_video; -- 请替换为实际数据库名称

-- 检查字段是否存在，如果不存在则添加
SET @db_name = DATABASE();
SET @table_name = 'projects';

-- 添加summary字段
SET @column_exists = (
    SELECT COUNT(*)
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = @db_name
      AND TABLE_NAME = @table_name
      AND COLUMN_NAME = 'summary'
);

IF @column_exists = 0 THEN
    ALTER TABLE projects
    ADD COLUMN summary VARCHAR(200) COMMENT '对话摘要，用于侧边栏展示';
END IF;

SELECT 'projects表添加summary字段完成' AS result;
