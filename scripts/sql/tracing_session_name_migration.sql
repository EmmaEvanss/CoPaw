-- ============================================================
-- Tracing Session Name Migration
-- Date: 2026-05-12
-- Description: Add session_name field to swe_tracing_traces table
-- ============================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- -----------------------------------------------------------
-- Migration: Add session_name to swe_tracing_traces table
-- -----------------------------------------------------------

-- 添加 session_name 字段
ALTER TABLE `swe_tracing_traces`
ADD COLUMN IF NOT EXISTS `session_name` VARCHAR(256) DEFAULT NULL
COMMENT '会话名称（从第一条消息提取）'
AFTER `session_id`;

-- -----------------------------------------------------------
-- 验证迁移结果
-- -----------------------------------------------------------
-- 查看 swe_tracing_traces 表结构
SHOW FULL COLUMNS FROM `swe_tracing_traces`;

-- 查看索引
SHOW INDEX FROM `swe_tracing_traces`;

SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================
-- 执行前请确认：
-- 1. 已备份数据库
-- 2. 已在测试环境验证
-- ============================================================
