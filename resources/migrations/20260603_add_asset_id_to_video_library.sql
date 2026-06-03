-- 为video_library表增加asset_id字段，关联到assets表
ALTER TABLE video_library
ADD COLUMN asset_id BIGINT NULL COMMENT '关联的内部资产ID' AFTER parsing_error,
ADD CONSTRAINT fk_video_library_asset_id FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE SET NULL,
ADD INDEX idx_asset_id (asset_id);
