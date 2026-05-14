-- ============================================================
-- Tracing User Info Migration
-- Date: 2026-05-07
-- Description: Add user_name and bbk_id fields to tracing tables
-- ============================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- -----------------------------------------------------------
-- Migration 1: Add user_name and bbk_id to swe_tracing_traces table
-- -----------------------------------------------------------

-- 添加 user_name 字段
ALTER TABLE `swe_tracing_traces`
ADD COLUMN IF NOT EXISTS `user_name` VARCHAR(128) DEFAULT NULL
COMMENT '用户姓名'
AFTER `user_id`;

-- 添加 bbk_id 字段
ALTER TABLE `swe_tracing_traces`
ADD COLUMN IF NOT EXISTS `bbk_id` VARCHAR(64) DEFAULT NULL
COMMENT '分行编号'
AFTER `user_name`;

-- 添加 user_name 索引
ALTER TABLE `swe_tracing_traces`
ADD INDEX IF NOT EXISTS `idx_user_name` (`user_name`);

-- 添加 bbk_id 索引
ALTER TABLE `swe_tracing_traces`
ADD INDEX IF NOT EXISTS `idx_bbk_id` (`bbk_id`);

-- -----------------------------------------------------------
-- Migration 2: Add user_name and bbk_id to swe_tracing_spans table
-- -----------------------------------------------------------

-- 添加 user_name 字段（冗余存储）
ALTER TABLE `swe_tracing_spans`
ADD COLUMN IF NOT EXISTS `user_name` VARCHAR(128) DEFAULT NULL
COMMENT '用户姓名（冗余）'
AFTER `user_id`;

-- 添加 bbk_id 字段（冗余存储）
ALTER TABLE `swe_tracing_spans`
ADD COLUMN IF NOT EXISTS `bbk_id` VARCHAR(64) DEFAULT NULL
COMMENT '分行编号（冗余）'
AFTER `user_name`;

-- 添加 bbk_id 索引（spans 表只需要 bbk_id 索引）
ALTER TABLE `swe_tracing_spans`
ADD INDEX IF NOT EXISTS `idx_bbk_id` (`bbk_id`);

-- -----------------------------------------------------------
-- 验证迁移结果
-- -----------------------------------------------------------
-- 查看 swe_tracing_traces 表结构
SHOW FULL COLUMNS FROM `swe_tracing_traces`;

-- 查看 swe_tracing_spans 表结构
SHOW FULL COLUMNS FROM `swe_tracing_spans`;

-- 查看索引
SHOW INDEX FROM `swe_tracing_traces`;
SHOW INDEX FROM `swe_tracing_spans`;

SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================
-- 执行前请确认：
-- 1. 已备份数据库
-- 2. 已在测试环境验证
-- ============================================================