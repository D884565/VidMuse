ALTER TABLE assets
    ADD COLUMN content_text TEXT NULL COMMENT 'Text material content',
    ADD COLUMN storage_key VARCHAR(500) NULL COMMENT 'Object storage key',
    ADD COLUMN file_hash VARCHAR(128) NULL COMMENT 'File hash',
    ADD COLUMN upload_status VARCHAR(20) NULL COMMENT 'Upload status',
    ADD COLUMN upload_session_id VARCHAR(64) NULL COMMENT 'Current upload session ID',
    ADD COLUMN chunk_size INT NULL COMMENT 'Chunk size',
    ADD COLUMN total_chunks INT NULL COMMENT 'Total chunks';

CREATE TABLE IF NOT EXISTS asset_upload_sessions (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    session_id VARCHAR(64) NOT NULL UNIQUE COMMENT 'Upload session ID',
    asset_id BIGINT NULL COMMENT 'Related asset ID',
    mode VARCHAR(20) NOT NULL COMMENT 'Mode: create/replace',
    file_name VARCHAR(255) NOT NULL COMMENT 'File name',
    file_hash VARCHAR(128) NOT NULL COMMENT 'File hash',
    file_size BIGINT NOT NULL COMMENT 'File size in bytes',
    chunk_size INT NOT NULL COMMENT 'Chunk size',
    total_chunks INT NOT NULL COMMENT 'Total chunks',
    uploaded_chunks INT NOT NULL DEFAULT 0 COMMENT 'Uploaded chunk count',
    status VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT 'Session status',
    redis_bitmap_key VARCHAR(255) NOT NULL COMMENT 'Redis bitmap key',
    temp_dir VARCHAR(500) NOT NULL COMMENT 'Temporary chunk directory',
    expires_at DATETIME NULL COMMENT 'Expiry time',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_asset_upload_sessions_asset_id
        FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE SET NULL
);
