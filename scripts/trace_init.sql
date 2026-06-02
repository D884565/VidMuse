-- 全链路追踪系统数据库初始化脚本
-- 创建时间：2026-06-01

-- 使用数据库（根据实际情况修改数据库名）
USE vidmuse;

-- 创建traces表：请求链路主表
CREATE TABLE `traces` (
    `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `trace_id` varchar(32) NOT NULL COMMENT '链路唯一标识',
    `method` varchar(10) NOT NULL COMMENT 'HTTP方法',
    `path` varchar(500) NOT NULL COMMENT '请求路径',
    `status_code` int NOT NULL COMMENT '响应状态码',
    `duration_ms` decimal(10,2) NOT NULL COMMENT '总耗时(毫秒)',
    `client_ip` varchar(64) DEFAULT NULL COMMENT '客户端IP',
    `user_id` int DEFAULT NULL COMMENT '用户ID',
    `user_agent` text DEFAULT NULL COMMENT '用户代理',
    `request_headers` json DEFAULT NULL COMMENT '请求头',
    `response_headers` json DEFAULT NULL COMMENT '响应头',
    `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_trace_id` (`trace_id`),
    KEY `idx_trace_created_at` (`created_at`),
    KEY `idx_trace_path` (`path`),
    KEY `idx_trace_user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='请求链路主表';

-- 创建spans表：函数调用Span表
CREATE TABLE `spans` (
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

-- 可选：添加外键约束（高并发场景建议不添加）
-- ALTER TABLE `spans` ADD CONSTRAINT `fk_spans_trace_id` FOREIGN KEY (`trace_id`) REFERENCES `traces` (`trace_id`) ON DELETE CASCADE;
