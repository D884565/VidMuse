-- 商品资产关联表迁移脚本
-- 执行时间：2024-06-06
-- 功能：建立商品与资产的多对多关联关系

CREATE TABLE IF NOT EXISTS product_assets (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '主键ID',
    product_id BIGINT NOT NULL COMMENT '关联商品ID',
    asset_id BIGINT NOT NULL COMMENT '关联资产ID',
    role VARCHAR(50) NOT NULL DEFAULT 'image' COMMENT '资产角色：main-主素材, image-普通图片, video-视频, audio-音频',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    UNIQUE KEY uq_product_assets_product_asset_role (product_id, asset_id, role),
    FOREIGN KEY fk_product_assets_product_id (product_id) REFERENCES products(id) ON DELETE CASCADE,
    FOREIGN KEY fk_product_assets_asset_id (asset_id) REFERENCES assets(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品资产关联表';

-- 索引优化
CREATE INDEX idx_product_assets_product_id ON product_assets(product_id);
CREATE INDEX idx_product_assets_asset_id ON product_assets(asset_id);
CREATE INDEX idx_product_assets_role ON product_assets(role);
