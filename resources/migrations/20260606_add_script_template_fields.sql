-- 剧本表新增灵感模板关联字段迁移脚本
-- 执行前请备份数据库

USE your_database_name; -- 请替换为实际数据库名称

-- 检查字段是否存在，如果不存在则添加
SET @db_name = DATABASE();
SET @table_name = 'scripts';

-- 添加template_id字段
SET @column_exists = (
    SELECT COUNT(*)
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = @db_name
      AND TABLE_NAME = @table_name
      AND COLUMN_NAME = 'template_id'
);

IF @column_exists = 0 THEN
    ALTER TABLE scripts
    ADD COLUMN template_id VARCHAR(32) NULL COMMENT '关联的灵感模板ID' AFTER generation_mode;
END IF;

-- 添加strategy_id字段
SET @column_exists = (
    SELECT COUNT(*)
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = @db_name
      AND TABLE_NAME = @table_name
      AND COLUMN_NAME = 'strategy_id'
);

IF @column_exists = 0 THEN
    ALTER TABLE scripts
    ADD COLUMN strategy_id VARCHAR(32) NULL COMMENT '关联的创作策略ID' AFTER template_id;
END IF;

-- 添加used_factors字段
SET @column_exists = (
    SELECT COUNT(*)
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = @db_name
      AND TABLE_NAME = @table_name
      AND COLUMN_NAME = 'used_factors'
);

IF @column_exists = 0 THEN
    ALTER TABLE scripts
    ADD COLUMN used_factors JSON NULL COMMENT '使用的因子列表，包含因子ID和参数值' AFTER strategy_id;
END IF;

-- 添加template_params字段
SET @column_exists = (
    SELECT COUNT(*)
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = @db_name
      AND TABLE_NAME = @table_name
      AND COLUMN_NAME = 'template_params'
);

IF @column_exists = 0 THEN
    ALTER TABLE scripts
    ADD COLUMN template_params JSON NULL COMMENT '用户对模板的自定义参数' AFTER used_factors;
END IF;

-- 添加template_id索引
SET @index_exists = (
    SELECT COUNT(*)
    FROM INFORMATION_SCHEMA.STATISTICS
    WHERE TABLE_SCHEMA = @db_name
      AND TABLE_NAME = @table_name
      AND INDEX_NAME = 'idx_template_id'
);

IF @index_exists = 0 THEN
    ALTER TABLE scripts
    ADD INDEX idx_template_id (template_id);
END IF;

-- 添加strategy_id索引
SET @index_exists = (
    SELECT COUNT(*)
    FROM INFORMATION_SCHEMA.STATISTICS
    WHERE TABLE_SCHEMA = @db_name
      AND TABLE_NAME = @table_name
      AND INDEX_NAME = 'idx_strategy_id'
);

IF @index_exists = 0 THEN
    ALTER TABLE scripts
    ADD INDEX idx_strategy_id (strategy_id);
END IF;

-- 添加唯一约束
SET @constraint_exists = (
    SELECT COUNT(*)
    FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
    WHERE TABLE_SCHEMA = @db_name
      AND TABLE_NAME = @table_name
      AND CONSTRAINT_NAME = 'uq_scripts_project_version'
);

IF @constraint_exists = 0 THEN
    ALTER TABLE scripts
    ADD UNIQUE KEY uq_scripts_project_version (project_id, version);
END IF;

-- 更新generation_mode的注释，添加template选项
ALTER TABLE scripts
MODIFY COLUMN generation_mode VARCHAR(20) COMMENT '生成模式: rag/manual/hybrid/template';

SELECT 'scripts表结构更新完成' AS result;
