-- 添加 projects 表的 music_config 字段
ALTER TABLE projects
ADD COLUMN music_config JSON COMMENT '音乐配置，如当前 BGM ID'
AFTER voice_type;
