-- 为video_library表添加与product_categories的关联字段
ALTER TABLE video_library
ADD COLUMN category_id BIGINT NULL COMMENT '关联分类ID，对应product_categories.id' AFTER category,
ADD COLUMN category_path VARCHAR(200) NULL COMMENT '分类路径，冗余存储方便检索，如"/1/2/3/"' AFTER category_id,
ADD INDEX idx_category_id (category_id),
ADD CONSTRAINT fk_video_library_category_id FOREIGN KEY (category_id) REFERENCES product_categories(id) ON DELETE SET NULL;
