DROP TABLE IF EXISTS spans;
DROP TABLE IF EXISTS traces;
DROP TABLE IF EXISTS agent_traces;

DROP TABLE IF EXISTS trace_log;
DROP TABLE IF EXISTS conversations;
DROP TABLE IF EXISTS generation_task_steps;
DROP TABLE IF EXISTS generation_tasks;
DROP TABLE IF EXISTS scripts;
DROP TABLE IF EXISTS frames;
DROP TABLE IF EXISTS merge_tasks;
DROP TABLE IF EXISTS slices;
DROP TABLE IF EXISTS project_assets;
DROP TABLE IF EXISTS assets;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS product_categories;
DROP TABLE IF EXISTS projects;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS pipeline_executions;



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
    summary         VARCHAR(200) COMMENT '对话摘要，用于侧边栏展示',
    workflow_stage  VARCHAR(30) NOT NULL DEFAULT 'created' COMMENT '工作流阶段: created/script/images/video/completed',
    stage_status    VARCHAR(30) NOT NULL DEFAULT 'idle' COMMENT '阶段状态: idle/running/done/failed',
    last_task_id    BIGINT COMMENT '最近一次异步任务ID',
    dirty_stage     VARCHAR(30) COMMENT '脏数据阶段标记',
    script_confirmed_at DATETIME COMMENT '剧本确认时间',
    images_confirmed_at DATETIME COMMENT '图片确认时间',
    video_confirmed_at  DATETIME COMMENT '视频确认时间',
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
    tags            JSON COMMENT '素材标签',
    scope           VARCHAR(30) NOT NULL DEFAULT 'library' COMMENT 'library/project/output',
    metadata        JSON COMMENT '素材扩展元数据',
    source_type     TINYINT DEFAULT 0 COMMENT '来源',
    parsing_status  VARCHAR(20) COMMENT '解析状态：pending/running/completed/failed',
    execution_id    VARCHAR(64) COMMENT '流水线执行ID，用于断点续跑',
    parsing_error   TEXT COMMENT '解析错误信息',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    INDEX idx_parsing_status (parsing_status),
    INDEX idx_execution_id (execution_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='素材库';


CREATE TABLE IF NOT EXISTS project_assets (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '项目素材绑定ID',
    project_id      BIGINT NOT NULL COMMENT '项目ID',
    asset_id        BIGINT NOT NULL COMMENT '素材ID',
    role            VARCHAR(50) NOT NULL DEFAULT 'reference' COMMENT '素材在项目中的用途',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE CASCADE,
    INDEX idx_project_assets_project (project_id),
    INDEX idx_project_assets_asset (asset_id),
    UNIQUE KEY uq_project_assets_project_asset_role (project_id, asset_id, role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='项目素材绑定表';


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
    script_id       BIGINT COMMENT '关联的剧本ID',
    sequence        INT NOT NULL COMMENT '帧序号(第几帧)',
    scene_type      TINYINT COMMENT '场景类型: 0-开场, 1-商品展示, 2-口播, 3-转场, 4-结尾',
    description     TEXT COMMENT '帧描述/画面描述',
    narration       TEXT COMMENT '旁白/口播文案',
    prompt          TEXT COMMENT '生成该帧的AI提示词',
    image_prompt    TEXT COMMENT '图片生成提示词',
    video_prompt    TEXT COMMENT '视频生成提示词',
    image_url       VARCHAR(500) COMMENT '帧图片URL',
    audio_url       VARCHAR(500) COMMENT '帧配音/音效URL',
    video_url       VARCHAR(500) COMMENT '帧视频URL',
    text_overlay    VARCHAR(500) COMMENT '叠加文字内容',
    subtitle_text   VARCHAR(500) COMMENT '字幕文本',
    subtitle_position VARCHAR(30) COMMENT '字幕位置: top/center/bottom',
    duration        DECIMAL(6, 3) DEFAULT 3.000 COMMENT '该帧持续时间(秒)',
    transition_type TINYINT DEFAULT 0 COMMENT '转场类型: 0-无, 1-淡入, 2-滑动, 3-缩放',
    status          TINYINT DEFAULT 0 COMMENT '状态: 0-待生成, 1-生成中, 2-已完成, 3-失败',
    error_message   TEXT COMMENT '生成失败的错误信息',
    dirty           INT NOT NULL DEFAULT 0 COMMENT '脏数据标记: 0-干净, 1-已修改',
    last_edited_at  DATETIME COMMENT '最后编辑时间',
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
    auto_parse      TINYINT(1) DEFAULT 0 COMMENT '是否创建后自动触发解析',
    images          JSON COMMENT '商品图片URL列表',
    parsing_status  VARCHAR(20) COMMENT '解析状态：pending/running/completed/failed',
    execution_id    VARCHAR(64) COMMENT '流水线执行ID，用于断点续跑',
    parsing_error   TEXT COMMENT '解析错误信息',
    ai_features     JSON COMMENT 'AI解析结果特征',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (category_id) REFERENCES product_categories(id) ON DELETE SET NULL,
    INDEX idx_user (user_id),
    INDEX idx_platform (platform, platform_id),
    INDEX idx_category (category),
    INDEX idx_category_id (category_id),
    INDEX idx_category_path (category_path),
    INDEX idx_parsing_status (parsing_status),
    INDEX idx_execution_id (execution_id),
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
    role            VARCHAR(20) NOT NULL COMMENT 'user/assistant/system',
    content         TEXT NOT NULL COMMENT '消息内容',
    message_type    VARCHAR(50) COMMENT '消息类型: text/script/image/video/action',
    stage           VARCHAR(50) COMMENT '所属工作流阶段: script/images/video',
    blocks          JSON COMMENT '结构化内容块',
    action_type     VARCHAR(50) COMMENT '动作类型: confirm/regenerate/edit',
    task_id         BIGINT COMMENT '关联的异步任务ID',
    metadata        JSON COMMENT '扩展元数据',
    frame_id        BIGINT COMMENT '关联帧ID',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (frame_id) REFERENCES frames(id) ON DELETE SET NULL,
    INDEX idx_conversations_project (project_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='对话记录表';


CREATE TABLE IF NOT EXISTS scripts (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '剧本ID',
    project_id      BIGINT NOT NULL COMMENT '所属项目ID',
    version         INT NOT NULL DEFAULT 1 COMMENT '版本号',
    status          VARCHAR(20) NOT NULL DEFAULT 'active' COMMENT '状态: active/archived',
    generation_mode VARCHAR(20) COMMENT '生成模式: rag/manual/hybrid',
    prompt_snapshot JSON COMMENT '生成时的提示词快照',
    rag_snapshot    JSON COMMENT 'RAG检索结果快照',
    content         JSON COMMENT '剧本内容（帧列表JSON）',
    parent_id       BIGINT COMMENT '父脚本版本ID',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_id) REFERENCES scripts(id),
    INDEX idx_project_id (project_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='剧本版本表';


CREATE TABLE IF NOT EXISTS generation_tasks (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '任务ID',
    project_id      BIGINT NOT NULL COMMENT '所属项目ID',
    task_type       VARCHAR(50) NOT NULL COMMENT '任务类型: script/image/video/tts',
    status          VARCHAR(20) NOT NULL DEFAULT 'queued' COMMENT '状态: queued/running/completed/failed/cancelled',
    celery_task_id  VARCHAR(200) COMMENT 'Celery异步任务ID',
    progress        INT NOT NULL DEFAULT 0 COMMENT '任务进度百分比',
    current_step    VARCHAR(80) COMMENT '当前执行步骤',
    current_frame_id BIGINT COMMENT '当前处理分镜ID',
    retry_count     INT NOT NULL DEFAULT 0 COMMENT '重试次数',
    error_code      VARCHAR(80) COMMENT '错误码',
    error_message   TEXT COMMENT '失败原因',
    trace_id        VARCHAR(100) COMMENT '链路追踪ID',
    result_data     JSON COMMENT '任务结果数据',
    started_at      DATETIME COMMENT '开始时间',
    finished_at     DATETIME COMMENT '结束时间',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    INDEX idx_project_id (project_id),
    INDEX idx_status (status),
    INDEX idx_generation_tasks_celery (celery_task_id),
    INDEX idx_generation_tasks_trace (trace_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='异步生成任务表';


CREATE TABLE IF NOT EXISTS generation_task_steps (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '任务步骤ID',
    task_id         BIGINT NOT NULL COMMENT '所属任务ID',
    step_name       VARCHAR(80) NOT NULL COMMENT '步骤名称',
    frame_id        BIGINT COMMENT '关联分镜ID',
    status          VARCHAR(30) NOT NULL DEFAULT 'running' COMMENT '步骤状态',
    progress        INT NOT NULL DEFAULT 0 COMMENT '步骤进度百分比',
    input_snapshot  JSON COMMENT '步骤输入快照',
    output_snapshot JSON COMMENT '步骤输出快照',
    error_message   TEXT COMMENT '错误信息',
    started_at      DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '开始时间',
    finished_at     DATETIME COMMENT '结束时间',
    FOREIGN KEY (task_id) REFERENCES generation_tasks(id) ON DELETE CASCADE,
    INDEX idx_generation_task_steps_task (task_id),
    INDEX idx_generation_task_steps_frame (frame_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='生成任务步骤表';


CREATE TABLE IF NOT EXISTS trace_log (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '日志ID',
    request_id      VARCHAR(50) COMMENT '请求ID',
    method          VARCHAR(10) COMMENT 'HTTP方法',
    path            VARCHAR(500) COMMENT '请求路径',
    status_code     INT COMMENT '响应状态码',
    duration_ms     FLOAT COMMENT '请求耗时(毫秒)',
    span_tree       JSON COMMENT '调用链路树',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_request_id (request_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='请求链路追踪日志';


CREATE TABLE IF NOT EXISTS agent_traces (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '推理轨迹ID',
    session_id      VARCHAR(64) NOT NULL COMMENT '会话ID',
    user_id         BIGINT COMMENT '用户ID',
    project_id      BIGINT COMMENT '项目ID',
    user_input      TEXT NOT NULL COMMENT '用户原始输入',
    system_prompt   TEXT NOT NULL COMMENT '系统提示词',
    model           VARCHAR(64) NOT NULL COMMENT '使用的模型名称',
    temperature     FLOAT NOT NULL COMMENT '模型温度参数',
    max_tokens      BIGINT NOT NULL COMMENT '最大生成长度',
    top_p           FLOAT NOT NULL COMMENT '核采样参数',
    messages_history JSON NOT NULL COMMENT '完整的消息历史',
    iterations      BIGINT NOT NULL DEFAULT 0 COMMENT '推理迭代次数',
    tool_calls      JSON COMMENT '所有工具调用信息',
    tool_results    JSON COMMENT '所有工具返回结果',
    final_answer    TEXT COMMENT '最终回答内容',
    cost_time       FLOAT NOT NULL COMMENT '执行耗时(秒)',
    success         TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否执行成功：1-成功，0-失败',
    error_msg       TEXT COMMENT '错误信息',
    meta_data        JSON COMMENT '扩展元数据',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    INDEX idx_agent_traces_session_id (session_id),
    INDEX idx_agent_traces_user_id (user_id),
    INDEX idx_agent_traces_project_id (project_id),
    INDEX idx_agent_traces_created_at (created_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Agent推理轨迹表';


CREATE TABLE IF NOT EXISTS pipeline_executions (
    id                  BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '主键ID',
    execution_id        VARCHAR(64) NOT NULL COMMENT '执行ID，全局唯一',
    pipeline_name       VARCHAR(100) NOT NULL COMMENT '流水线名称',
    pipeline_type       VARCHAR(50) NOT NULL COMMENT '流水线类型：video/product/video_overall',
    status              VARCHAR(20) NOT NULL COMMENT '执行状态：pending/running/completed/failed/cancelled',
    current_processor_index INT NOT NULL COMMENT '当前执行到的处理器索引',
    total_processors    INT NOT NULL COMMENT '总处理器数量',
    input_params        JSON NOT NULL COMMENT '初始输入参数',
    context_data        JSON COMMENT '上下文数据快照',
    context_metadata    JSON COMMENT '上下文元数据快照',
    errors              JSON COMMENT '错误信息列表',
    error_message       TEXT COMMENT '最后一次错误信息',
    result              JSON COMMENT '最终执行结果',
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    completed_at        TIMESTAMP NULL COMMENT '完成时间',

    UNIQUE KEY uk_execution_id (execution_id),
    INDEX idx_pipeline_type (pipeline_type),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='流水线执行记录表';

-- ----------------------------
-- 灵感模板模块相关表
-- ----------------------------

DROP TABLE IF EXISTS factors;
CREATE TABLE IF NOT EXISTS factors (
    id                  BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '主键ID',
    factor_id           VARCHAR(32) NOT NULL COMMENT '全局唯一因子ID',
    factor_type         VARCHAR(50) NOT NULL COMMENT '因子类型：content_structure/product_expression/user_operation',
    name                VARCHAR(100) NOT NULL COMMENT '因子名称',
    description         TEXT COMMENT '因子详细描述',
    applicable_scenarios JSON COMMENT '适用场景列表',
    data_schema         JSON COMMENT '因子数据结构定义',
    example             JSON COMMENT '因子示例数据',
    tags                JSON COMMENT '标签列表',
    popularity          DECIMAL(4, 3) NOT NULL DEFAULT 0.0 COMMENT '流行度，0-1之间',
    usage_count         INT NOT NULL DEFAULT 0 COMMENT '使用次数统计',
    is_deleted          TINYINT NOT NULL DEFAULT 0 COMMENT '是否删除：0-未删除，1-已删除',
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    UNIQUE KEY uk_factor_id (factor_id, is_deleted),
    INDEX idx_factor_type (factor_type),
    INDEX idx_popularity (popularity),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='创作因子表';


DROP TABLE IF EXISTS strategies;
CREATE TABLE IF NOT EXISTS strategies (
    id                  BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '主键ID',
    strategy_id         VARCHAR(32) NOT NULL COMMENT '全局唯一策略ID',
    name                VARCHAR(100) NOT NULL COMMENT '策略名称',
    description         TEXT COMMENT '策略详细描述',
    applicable_scenarios JSON COMMENT '适用场景列表',
    core_logic          TEXT COMMENT '核心创作逻辑描述',
    required_factor_types JSON COMMENT '必填因子类型列表',
    optional_factor_types JSON COMMENT '可选因子类型列表',
    combination_rules   TEXT COMMENT '因子组合规则描述',
    success_rate        DECIMAL(4, 3) NOT NULL DEFAULT 0.0 COMMENT '历史爆款成功率，0-1之间',
    tags                JSON COMMENT '标签列表',
    usage_count         INT NOT NULL DEFAULT 0 COMMENT '使用次数统计',
    is_deleted          TINYINT NOT NULL DEFAULT 0 COMMENT '是否删除：0-未删除，1-已删除',
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    UNIQUE KEY uk_strategy_id (strategy_id, is_deleted),
    INDEX idx_success_rate (success_rate),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='创作策略表';


DROP TABLE IF EXISTS inspiration_templates;
CREATE TABLE IF NOT EXISTS inspiration_templates (
    id                  BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '主键ID',
    template_id         VARCHAR(32) NOT NULL COMMENT '全局唯一模板ID',
    strategy_id         VARCHAR(32) NOT NULL COMMENT '关联的策略ID',
    name                VARCHAR(100) NOT NULL COMMENT '模板名称',
    description         TEXT COMMENT '模板描述',
    combination_example JSON COMMENT '完整组合示例',
    version             VARCHAR(20) NOT NULL DEFAULT 'v1.0' COMMENT '版本号',
    success_rate        DECIMAL(4, 3) NOT NULL DEFAULT 0.0 COMMENT '模板成功率，0-1之间',
    usage_count         INT NOT NULL DEFAULT 0 COMMENT '使用次数统计',
    is_deleted          TINYINT NOT NULL DEFAULT 0 COMMENT '是否删除：0-未删除，1-已删除',
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    UNIQUE KEY uk_template_id (template_id, is_deleted),
    INDEX idx_strategy_id (strategy_id),
    INDEX idx_version (version),
    INDEX idx_success_rate (success_rate),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='灵感模板表';


DROP TABLE IF EXISTS template_factor_relations;
CREATE TABLE IF NOT EXISTS template_factor_relations (
    id                  BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '主键ID',
    template_id         VARCHAR(32) NOT NULL COMMENT '模板ID',
    factor_id           VARCHAR(32) NOT NULL COMMENT '因子ID',
    factor_usage_type   TINYINT NOT NULL COMMENT '因子使用类型：1-必填，2-可选',
    sort_order          INT NOT NULL DEFAULT 0 COMMENT '排序权重',
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',

    UNIQUE KEY uk_template_factor (template_id, factor_id),
    INDEX idx_template_id (template_id),
    INDEX idx_factor_id (factor_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='模板-因子关联表';

-- ----------------------------
-- 全链路追踪系统相关表
-- ----------------------------

-- traces表：请求链路主表
CREATE TABLE IF NOT EXISTS `traces` (
    `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `trace_id` varchar(32) NOT NULL COMMENT '链路唯一标识',
    `user_id` int DEFAULT NULL COMMENT '用户ID',
    `method` varchar(10) NOT NULL COMMENT 'HTTP方法',
    `path` varchar(500) NOT NULL COMMENT '请求路径',
    `status_code` int NOT NULL COMMENT '响应状态码',
    `duration_ms` decimal(10,2) NOT NULL COMMENT '总耗时(毫秒)',
    `client_ip` varchar(64) DEFAULT NULL COMMENT '客户端IP',
    `user_agent` text DEFAULT NULL COMMENT '用户代理',
    `request_headers` json DEFAULT NULL COMMENT '请求头',
    `response_headers` json DEFAULT NULL COMMENT '响应头',
    `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_trace_id` (`trace_id`),
    KEY `idx_trace_created_at` (`created_at`),
    KEY `idx_trace_path` (`path`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='请求链路主表';

-- spans表：函数调用Span表
CREATE TABLE IF NOT EXISTS `spans` (
    `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `trace_id` varchar(32) NOT NULL COMMENT '所属链路ID',
    `span_id` varchar(16) NOT NULL COMMENT 'Span唯一标识',
    `parent_span_id` varchar(16) DEFAULT NULL COMMENT '父Span ID',
    `name` varchar(255) NOT NULL COMMENT '函数名/操作名',
    `class_name` varchar(255) DEFAULT NULL COMMENT '类名',
    `module_name` varchar(255) NOT NULL COMMENT '模块名',
    `start_time` decimal(16,6) NOT NULL COMMENT '开始时间戳(秒)',
    `end_time` decimal(16,6) NOT NULL COMMENT '结束时间戳(秒)',
    `duration_ms` decimal(10,2) NOT NULL COMMENT '耗时(毫秒)',
    `args` json DEFAULT NULL COMMENT '位置参数',
    `kwargs` json DEFAULT NULL COMMENT '关键字参数',
    `return_value` json DEFAULT NULL COMMENT '返回值',
    `exception` text DEFAULT NULL COMMENT '异常信息',
    `stack_trace` text DEFAULT NULL COMMENT '调用堆栈',
    `meta_data` json DEFAULT NULL COMMENT '扩展元数据',
    `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    KEY `idx_span_trace_id` (`trace_id`),
    KEY `idx_span_parent_id` (`parent_span_id`),
    KEY `idx_span_name` (`name`),
    KEY `idx_span_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='函数调用Span表';



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




-- 创建内部视频素材库表
CREATE TABLE IF NOT EXISTS video_library (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '主键ID',
    title VARCHAR(200) NULL COMMENT '视频标题',
    description TEXT NULL COMMENT '视频描述',
    url VARCHAR(500) NOT NULL COMMENT '视频存储URL',
    cover_url VARCHAR(500) NULL COMMENT '封面图URL',
    file_size BIGINT NULL COMMENT '文件大小(字节)',
    duration INT NULL COMMENT '视频时长(秒)',
    format VARCHAR(20) NULL COMMENT '文件格式',
    source_type INT NOT NULL DEFAULT 0 COMMENT '来源：0-内部上传, 1-爆款抓取, 2-人工录入, 3-其他',
    hot_score INT NULL COMMENT '爆款分数(0-100)',
    category VARCHAR(100) NULL COMMENT '视频分类/商品品类',
    tags JSON NULL COMMENT '视频标签数组',
    parsed_data JSON NULL COMMENT '结构化解析数据',
    parsing_status VARCHAR(20) NULL DEFAULT 'pending' COMMENT '解析状态：pending/running/completed/failed',
    execution_id VARCHAR(64) NULL COMMENT '流水线执行ID，用于断点续跑',
    parsing_error TEXT NULL COMMENT '解析错误信息',
    created_by BIGINT NOT NULL COMMENT '创建人ID(管理员ID)',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_category (category),
    INDEX idx_hot_score (hot_score),
    INDEX idx_source_type (source_type),
    INDEX idx_created_at (created_at),
    UNIQUE KEY uk_url (url)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='内部视频素材库表';



-- 为video_library表添加与product_categories的关联字段
ALTER TABLE video_library
ADD COLUMN category_id BIGINT NULL COMMENT '关联分类ID，对应product_categories.id' AFTER category,
ADD COLUMN category_path VARCHAR(200) NULL COMMENT '分类路径，冗余存储方便检索，如"/1/2/3/"' AFTER category_id,
ADD INDEX idx_category_id (category_id),
ADD CONSTRAINT fk_video_library_category_id FOREIGN KEY (category_id) REFERENCES product_categories(id) ON DELETE SET NULL;


-- 为video_library表增加asset_id字段，关联到assets表
ALTER TABLE video_library
ADD COLUMN asset_id BIGINT NULL COMMENT '关联的内部资产ID' AFTER parsing_error,
ADD CONSTRAINT fk_video_library_asset_id FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE SET NULL,
ADD INDEX idx_asset_id (asset_id);
