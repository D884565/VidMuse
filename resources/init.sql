DROP TABLE IF EXISTS conversations;
DROP TABLE IF EXISTS frames;
DROP TABLE IF EXISTS merge_tasks;
DROP TABLE IF EXISTS slices;
DROP TABLE IF EXISTS assets;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS product_categories;
DROP TABLE IF EXISTS projects;
DROP TABLE IF EXISTS users;



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


CREATE TABLE IF NOT EXISTS product_categories (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '分类ID',
    name            VARCHAR(100) NOT NULL COMMENT '分类名称',
    parent_id       BIGINT NOT NULL DEFAULT 0 COMMENT '父分类ID，0表示一级分类',
    level           TINYINT NOT NULL COMMENT '分类层级：1-一级分类，2-二级分类，3-三级分类',
    path            VARCHAR(200) NOT NULL COMMENT '分类路径，如"/1/2/3/"，方便查询子树',
    sort            INT NOT NULL DEFAULT 0 COMMENT '排序权重，数值越大越靠前',
    is_deleted      TINYINT NOT NULL DEFAULT 0 COMMENT '是否删除：0-未删除，1-已删除',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_name_parent (name, parent_id, is_deleted),
    INDEX idx_parent_id (parent_id),
    INDEX idx_level (level),
    INDEX idx_path (path)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品分类表';


CREATE TABLE IF NOT EXISTS projects (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '项目id',
    title           VARCHAR(200) NOT NULL COMMENT '项目标题',
    description     TEXT COMMENT '项目描述',
    product_url     VARCHAR(1000) COMMENT '商品链接',
    product_info    TEXT COMMENT '商品信息(爬取/LLM整理)',
    video_output_url VARCHAR(500) COMMENT '最终成片URL',
    audio_url       VARCHAR(500) COMMENT 'TTS配音音频URL',
    status          VARCHAR(20) DEFAULT 'draft' COMMENT '项目状态: draft/script_ready/processing/completed/failed',
    user_id         BIGINT COMMENT '用户id',
    product_id      BIGINT COMMENT '商品id',
    user_prompt     TEXT COMMENT '用户创作意图',
    reference_images JSON COMMENT '参考图片URL列表',
    style           VARCHAR(50) COMMENT '视频风格',
    target_audience VARCHAR(100) COMMENT '目标受众',
    key_points      JSON COMMENT '强调卖点列表',
    avoid           JSON COMMENT '避免内容列表',
    rag_weight      DECIMAL(3,2) NOT NULL DEFAULT 0.30 COMMENT 'RAG权重',
    target_duration INT NOT NULL DEFAULT 30 COMMENT '目标视频时长(秒)',
    voice_type      VARCHAR(50) NOT NULL DEFAULT 'zh_female_cancan_mars_bigtts' COMMENT '语音类型',
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


CREATE TABLE IF NOT EXISTS slices (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '切片id',
    asset_id        BIGINT NOT NULL COMMENT '所属资产id',
    `index`         INT NOT NULL COMMENT '切片序号(从1开始)',
    title           VARCHAR(200) COMMENT '切片标题',
    url             VARCHAR(500) NOT NULL COMMENT '切片视频URL',
    cover_url       VARCHAR(500) COMMENT '切片封面图URL',
    start_time      INT COMMENT '切片在原视频中的开始时间(毫秒)',
    end_time        INT COMMENT '切片在原视频中的结束时间(毫秒)',
    duration        INT COMMENT '切片时长(毫秒)',
    ai_features     JSON COMMENT 'AI特征因子',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE CASCADE,
    UNIQUE KEY uk_asset_index (asset_id, `index`),
    INDEX idx_asset_id (asset_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='视频切片表';


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
    category        VARCHAR(100) COMMENT '商品分类（冗余存储三级分类名称）',
    category_id     BIGINT COMMENT '关联分类ID，对应product_categories.id',
    category_path   VARCHAR(200) COMMENT '分类路径，冗余存储方便检索，如"/1/2/3/"',
    description     TEXT COMMENT '商品描述',
    selling_points  JSON COMMENT 'ai解析特征',
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
    FOREIGN KEY (category_id) REFERENCES product_categories(id) ON DELETE SET NULL,
    INDEX idx_user (user_id),
    INDEX idx_platform (platform, platform_id),
    INDEX idx_category (category),
    INDEX idx_category_id (category_id),
    INDEX idx_category_path (category_path),
    FULLTEXT INDEX ft_name_desc (name, description)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品表';



CREATE TABLE IF NOT EXISTS merge_tasks (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    task_id         VARCHAR(50) NOT NULL COMMENT '任务ID',
    task_type       VARCHAR(20) NOT NULL COMMENT '任务类型: audio_replace/bgm/mix',
    video_id        BIGINT NOT NULL COMMENT '视频资产ID',
    params          TEXT NOT NULL COMMENT '任务参数JSON',
    status          VARCHAR(20) NOT NULL DEFAULT 'queued' COMMENT 'queued/processing/completed/failed/cancelled',
    result          TEXT COMMENT '任务结果JSON',
    error_message   TEXT COMMENT '错误信息',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_task_id (task_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='音视频合成任务表';



CREATE TABLE IF NOT EXISTS conversations (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    project_id      BIGINT NOT NULL COMMENT '项目id',
    role            VARCHAR(20) NOT NULL COMMENT 'user/assistant',
    content         TEXT NOT NULL COMMENT '消息内容',
    frame_id        BIGINT COMMENT '关联帧ID',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (frame_id) REFERENCES frames(id) ON DELETE SET NULL,
    INDEX idx_conversations_project (project_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='对话记录表';