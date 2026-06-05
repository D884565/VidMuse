-- scripts/migrations/20260605_add_push_message_tables.sql
-- 创建推送消息表
CREATE TABLE IF NOT EXISTS push_messages (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    message_id VARCHAR(36) NOT NULL UNIQUE,
    message_type VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    content JSON NOT NULL,
    level VARCHAR(20) DEFAULT 'info',
    trace_id VARCHAR(64),
    extra JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_message_id (message_id),
    INDEX idx_message_type (message_type),
    INDEX idx_trace_id (trace_id),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='推送消息表';

-- 创建用户消息关联表
CREATE TABLE IF NOT EXISTS user_messages (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    message_id VARCHAR(36) NOT NULL,
    is_read TINYINT(1) DEFAULT 0,
    read_at DATETIME NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_message_id (message_id),
    INDEX idx_user_read (user_id, is_read),
    UNIQUE KEY uk_user_message (user_id, message_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户消息关联表';
