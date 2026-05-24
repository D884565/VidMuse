DROP TABLE IF EXISTS scripts;
DROP TABLE IF EXISTS projects;
DROP TABLE IF EXISTS materials;



CREATE TABLE IF NOT EXISTS users(
    id              BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '用户id',
    username        VARCHAR(50) NOT NULL COMMENT '用户名',
    password_hash   VARCHAR(255) NOT NULL COMMENT '密码哈希',
    avatar_url      VARCHAR(500) COMMENT '头像URL',
    role            TINYINT DEFAULT 1 COMMENT '角色: 0-超级管理员, 1-普通用户, 2-VIP用户',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_username (username),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表';



CREATE TABLE IF NOT EXISTS projects (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '项目id',
    title           VARCHAR(200) NOT NULL COMMENT '项目标题',
    description     TEXT COMMENT '项目描述',
    product_url     VARCHAR(1000) COMMENT '商品链接',
    video_output_url VARCHAR(500) COMMENT '最终成片URL',
    user_id         BIGINT COMMENT '用户id',
  	product_id      BIGINT COMMENT '商品id',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='视频项目表';



CREATE TABLE IF NOT EXISTS assets (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '资产id',
    user_id         BIGINT COMMENT '用户id',
    type            TINYINT NOT NULL COMMENT '资产类型',
    title           VARCHAR(200) COMMENT '资产标题',
    url             VARCHAR(500) NOT NULL COMMENT '存储URL',
    file_size       BIGINT COMMENT '文件大小(字节)',
    duration        INT COMMENT '时长(视频/音频)',
    format          VARCHAR(20) COMMENT '文件格式',
    ai_features     JSON COMMENT 'AI特征因子',
    source_type     TINYINT DEFAULT 0 COMMENT '来源',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='素材库';



CREATE TABLE IF NOT EXISTS frames (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '帧id',
    project_id      BIGINT NOT NULL COMMENT '项目id',
    sequence        INT NOT NULL COMMENT '帧序号(第几帧)',
    scene_type      TINYINT COMMENT '场景类型: 0-开场, 1-商品展示, 2-口播, 3-转场, 4-结尾',
    description     TEXT COMMENT '帧描述/画面描述',
    prompt          TEXT COMMENT '生成该帧的AI提示词',
    image_url       VARCHAR(500) COMMENT '帧图片URL',
    audio_url       VARCHAR(500) COMMENT '帧配音/音效URL',
    text_overlay    VARCHAR(500) COMMENT '叠加文字内容',
    duration        DECIMAL(6, 3) DEFAULT 3.000 COMMENT '该帧持续时间(秒)',
    transition_type TINYINT DEFAULT 0 COMMENT '转场类型: 0-无, 1-淡入, 2-滑动, 3-缩放',
    status          TINYINT DEFAULT 0 COMMENT '状态: 0-待生成, 1-生成中, 2-已完成, 3-失败',
    ai_params       JSON COMMENT 'AI生成参数',
    metadata        JSON COMMENT '额外元数据',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    UNIQUE KEY uk_project_sequence (project_id, sequence),
    INDEX idx_project_status (project_id, status),
    INDEX idx_scene_type (scene_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='视频帧表';



CREATE TABLE IF NOT EXISTS products (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '商品id',
    user_id         BIGINT COMMENT '所属用户id(为空表示平台公共商品)',
    name            VARCHAR(200) NOT NULL COMMENT '商品名称',
    brand           VARCHAR(100) COMMENT '品牌',
    category        VARCHAR(100) COMMENT '商品分类',
    description     TEXT COMMENT '商品描述',
    selling_points  JSON COMMENT '卖点列表',
    price           DECIMAL(12, 2) COMMENT '价格',
    main_image_url  VARCHAR(500) COMMENT '主图URL',
    detail_url      VARCHAR(1000) COMMENT '商品详情页链接',
    platform        VARCHAR(50) COMMENT '来源平台: taobao, jd, pdd, douyin等',
    platform_id     VARCHAR(100) COMMENT '平台商品ID',
    specs           JSON COMMENT '商品规格参数',
    tags            JSON COMMENT '标签',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_user (user_id),
    INDEX idx_platform (platform, platform_id),
    INDEX idx_category (category),
    FULLTEXT INDEX ft_name_desc (name, description)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品表';