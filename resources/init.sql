CREATE TABLE projects (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    title           VARCHAR(200) NOT NULL COMMENT '项目标题',
    description     TEXT COMMENT '项目描述',
    product_url     VARCHAR(1000) COMMENT '商品链接',
    product_image   VARCHAR(500) COMMENT '商品主图URL',
    product_info    TEXT COMMENT '商品信息解析结果（标题、价格、卖点等）',
    video_output_url VARCHAR(500) COMMENT '最终成片URL',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='视频项目表';


CREATE TABLE scripts (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    project_id      BIGINT NOT NULL COMMENT '所属项目',
    title           VARCHAR(200) COMMENT '剧本标题',
    content         TEXT NOT NULL COMMENT '剧本内容',
    target_duration INT COMMENT '目标时长(秒)',
    ai_model        VARCHAR(50) COMMENT '使用的AI模型',
    ai_prompt       TEXT COMMENT '生成使用的完整Prompt',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='剧本表';



CREATE TABLE materials (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    type            TINYINT NOT NULL COMMENT '素材类型',
    title           VARCHAR(200) COMMENT '素材标题',
    url             VARCHAR(500) NOT NULL COMMENT '存储URL',
    file_size       BIGINT COMMENT '文件大小(字节)',
    duration        INT COMMENT '时长(视频/音频)',
    format          VARCHAR(20) COMMENT '文件格式',
    ai_features     JSON COMMENT 'AI特征向量/描述（用于智能检索）',
    source_type     TINYINT DEFAULT 0 COMMENT '来源',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FULLTEXT INDEX ft_title_tags (title)  -- MySQL 5.6+ 支持
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='素材库';