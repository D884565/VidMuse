-- 为traces表添加user_id字段
-- 执行时间：2026-06-02
USE vidmuse;

ALTER TABLE `traces`
ADD COLUMN `user_id` int DEFAULT NULL COMMENT '用户ID' AFTER `client_ip`,
ADD KEY `idx_trace_user_id` (`user_id`);
