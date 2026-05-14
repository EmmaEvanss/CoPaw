# 应用市场数据库初始化计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 创建应用市场所需的3张新表，并对 `swe_tenant_init_source` 表新增2个字段。

**Architecture:** 所有 DDL 以独立 SQL 文件形式存放在 `scripts/sql/` 目录，遵循现有命名和格式规范（`CREATE TABLE IF NOT EXISTS`、`ENGINE=InnoDB`、`utf8mb4`、字段注释）。表变更使用单独的 migration 文件。

**Tech Stack:** MySQL / TDSQL，无 ORM，纯 SQL 文件。

---

## 文件结构

| 文件 | 说明 |
|------|------|
| `scripts/sql/marketplace_tables.sql` | 新建3张市场相关表 |
| `scripts/sql/migrate_tenant_init_source_bbk.sql` | `swe_tenant_init_source` 表新增 `bbk_id` 和 `tenant_name` 字段 |

---

### Task 1: 创建市场相关表 SQL 文件

**Files:**
- Create: `scripts/sql/marketplace_tables.sql`

- [ ] **Step 1: 创建 SQL 文件**

创建 `scripts/sql/marketplace_tables.sql`，内容如下：

```sql
-- ============================================================
-- 应用市场相关表
-- 包含：用户操作日志、市场操作日志、市场分类配置
-- ============================================================

-- 用户技能/MCP 操作日志
-- 记录用户对技能和 MCP 的创建、编辑、删除操作
CREATE TABLE IF NOT EXISTS swe_user_item_operation_logs (
    id           BIGINT AUTO_INCREMENT PRIMARY KEY,
    source_id    VARCHAR(64)  NOT NULL COMMENT '应用入口标识',
    user_id      VARCHAR(128) NOT NULL COMMENT '操作用户ID',
    user_name    VARCHAR(256)          COMMENT '操作用户名称',
    operation    VARCHAR(32)  NOT NULL COMMENT '操作类型：create/edit/delete',
    item_type    VARCHAR(16)  NOT NULL COMMENT '条目类型：skill/mcp',
    item_name    VARCHAR(256) NOT NULL COMMENT '条目名称',
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '操作时间',
    INDEX idx_source_id (source_id),
    INDEX idx_user_id (user_id),
    INDEX idx_item_type (item_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户技能/MCP操作日志';


-- 市场操作日志
-- 记录管理员对市场的上架、下架、分发操作
-- 分发时每个目标用户写一条记录（展开到用户粒度）
CREATE TABLE IF NOT EXISTS swe_marketplace_operation_logs (
    id               BIGINT AUTO_INCREMENT PRIMARY KEY,
    source_id        VARCHAR(64)  NOT NULL COMMENT '应用入口标识',
    operator_id      VARCHAR(64)  NOT NULL COMMENT '操作人用户ID',
    operator_name    VARCHAR(256)          COMMENT '操作人用户名称',
    operation        VARCHAR(32)  NOT NULL COMMENT '操作类型：publish/unpublish/distribute',
    item_type        VARCHAR(16)  NOT NULL COMMENT '条目类型：skill/mcp',
    item_id          VARCHAR(64)  NOT NULL COMMENT '市场条目ID',
    item_name        VARCHAR(256)          COMMENT '市场条目名称',
    target_user_id   VARCHAR(64)           COMMENT '分发目标用户ID',
    target_user_name VARCHAR(256)          COMMENT '分发目标用户名称',
    target_bbk_id    VARCHAR(64)           COMMENT '分发目标用户所属机构ID（快照）',
    created_at       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '操作时间',
    INDEX idx_source_id (source_id),
    INDEX idx_item_id (item_id),
    INDEX idx_target_user_id (target_user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='市场操作日志';


-- 市场技能分类配置
-- 按 source_id 隔离，暂不提供管理页面，直接操作数据库配置
CREATE TABLE IF NOT EXISTS swe_marketplace_categories (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    source_id   VARCHAR(64)  NOT NULL COMMENT '应用入口标识',
    name        VARCHAR(128) NOT NULL COMMENT '分类名称',
    sort_order  INT          NOT NULL DEFAULT 0 COMMENT '排序权重，升序',
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_source_id (source_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='市场技能分类配置';
```

- [ ] **Step 2: 验证 SQL 语法**

在 MySQL 客户端或本地环境执行，确认无语法错误：

```bash
mysql -u <user> -p <database> < scripts/sql/marketplace_tables.sql
```

预期：3张表创建成功，无报错。验证：

```sql
SHOW TABLES LIKE 'swe_marketplace%';
SHOW TABLES LIKE 'swe_user_item%';
```

预期输出包含：
```
swe_marketplace_categories
swe_marketplace_operation_logs
swe_user_item_operation_logs
```

- [ ] **Step 3: 验证表结构**

```sql
DESCRIBE swe_user_item_operation_logs;
DESCRIBE swe_marketplace_operation_logs;
DESCRIBE swe_marketplace_categories;
```

确认字段名、类型、注释与设计文档一致。

- [ ] **Step 4: Commit**

```bash
git add scripts/sql/marketplace_tables.sql
git commit -m "feat(marketplace): add marketplace database tables DDL"
```

---

### Task 2: swe_tenant_init_source 表字段扩展

**Files:**
- Create: `scripts/sql/migrate_tenant_init_source_bbk.sql`

- [ ] **Step 1: 确认现有表结构**

```sql
DESCRIBE swe_tenant_init_source;
```

确认表中尚不存在 `bbk_id` 和 `tenant_name` 字段，再执行后续步骤。

- [ ] **Step 2: 创建 migration SQL 文件**

创建 `scripts/sql/migrate_tenant_init_source_bbk.sql`，内容如下：

```sql
-- ============================================================
-- swe_tenant_init_source 表字段扩展
-- 新增 bbk_id（所属机构ID）和 tenant_name（用户名称）
-- 用于应用市场按机构维度分发技能时展开用户列表
-- ============================================================

ALTER TABLE swe_tenant_init_source
    ADD COLUMN bbk_id     VARCHAR(64)  DEFAULT NULL COMMENT '所属机构ID' AFTER source_id,
    ADD COLUMN tenant_name VARCHAR(256) DEFAULT NULL COMMENT '用户名称'   AFTER bbk_id;

-- 为 bbk_id 新增索引，支持按机构查询用户列表
ALTER TABLE swe_tenant_init_source
    ADD INDEX idx_bbk_id (bbk_id);
```

- [ ] **Step 3: 执行 migration**

```bash
mysql -u <user> -p <database> < scripts/sql/migrate_tenant_init_source_bbk.sql
```

预期：无报错。

- [ ] **Step 4: 验证字段新增成功**

```sql
DESCRIBE swe_tenant_init_source;
```

确认输出中包含：
```
bbk_id      varchar(64)   YES  MUL  NULL
tenant_name varchar(256)  YES       NULL
```

- [ ] **Step 5: Commit**

```bash
git add scripts/sql/migrate_tenant_init_source_bbk.sql
git commit -m "feat(marketplace): add bbk_id and tenant_name to swe_tenant_init_source"
```

---

## 自检

**Spec 覆盖：**
- [x] `swe_user_item_operation_logs` — Task 1
- [x] `swe_marketplace_operation_logs` — Task 1
- [x] `swe_marketplace_categories` — Task 1
- [x] `swe_tenant_init_source` 新增 `bbk_id` / `tenant_name` — Task 2

**占位符扫描：** 无 TBD/TODO，所有 SQL 完整。

**一致性：** 表名、字段名与设计文档 `2026-04-29-marketplace-design.md` 第三节完全一致。
