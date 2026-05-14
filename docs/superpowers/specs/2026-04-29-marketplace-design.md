# 应用市场功能设计文档

> 创建时间：2026-04-29
> 状态：已确认

---

## 一、需求概述

新建应用市场功能，包含**技能（Skills）**和 **MCP** 两部分。本期实现技能部分，MCP 部分留空占位由其他开发人员负责。

### 核心需求

| 功能点 | 说明 |
|--------|------|
| Source-ID 隔离 | 市场条目按 source-id 隔离，用户只能看到匹配自己 source-id 的条目 |
| bbk_id 过滤 | 总行（bbk_id=100）可见全部；分行用户只见总行技能和本分行技能 |
| 管理员分发 | 每个 source-id 有自己的管理员（manager 标识），可将技能分发到用户工作目录 |
| 应用市场页 | 所有用户可浏览，管理员额外拥有上架、下架、分发操作 |
| 我的技能菜单 | 新建"我的技能"菜单，左侧树状展示"我创建的"和"我接收的"，替代老 Skills 菜单功能 |
| 我的 MCP 菜单 | 新建"我的 MCP"菜单，留空占位，由其他开发人员负责 |
| 编辑权限 | 只有"我创建的"技能支持编辑保存 |
| 老菜单保留 | 老 Skills 和 MCP 菜单保持原名不变，与新菜单并存 |

---

## 二、架构总览

### 部署架构

market 是独立服务，代码位于仓库根目录 `market/src/`，使用 Python + FastAPI，与主服务（`src/swe/`）独立部署。

两者通过以下方式共享数据：
- **数据库**：共享同一 MySQL 实例，market 服务读写 `swe_*` 前缀表
- **文件系统**：通过 NAS 挂载共享，market 服务可直接读写 `~/.swe.marketplace/` 和 `~/.swe/<user_id>/` 目录

### 存储层

**文件系统（内容存储）**

```
~/.swe.marketplace/
└── <source_id>/
    ├── index.json              # 市场条目索引
    └── skills/
        └── <item_id>/          # 技能完整快照
            ├── skill.json
            └── SKILL.md
```

**数据库（操作日志）**

新增 `swe_marketplace_operation_logs` 表，记录所有写操作，支持分发记录查询和数据分析。

### 服务层

新增 `MarketplaceService`，职责：
- 市场技能 CRUD（管理员操作）
- 按 source-id + bbk-id 过滤内容
- 分发：通过 NAS 共享直接将市场内容写入目标用户的 `~/.swe/<user_id>/` 目录
- 写操作同步记录日志到数据库

### API 层

在 `market/src/` 下新增 FastAPI 路由，通过请求头 `X-Source-Id` 和 `manager` 标识做权限校验。

> **实施注意**：所有后端代码统一放在 `market/src/` 目录下；前端新增页面统一放在 `console/src/pages/Market/` 目录下。

### 前端层

- 新增**应用市场**页面（所有用户可见）：技能 tab + MCP tab（留空）
- 新增**我的技能**菜单（所有用户可见）：我创建的 / 我接收的
- 新增**我的 MCP** 菜单（留空占位）
- 老 Skills 和 MCP 菜单保持原名不变，与新菜单并存

---

## 三、数据模型

### 3.1 市场条目索引（index.json）

```json
{
  "items": [
    {
      "item_id": "uuid",
      "item_type": "skill",
      "name": "技能名称",
      "description": "描述",
      "version": "1.0.0",
      "creator_id": "user_id",
      "creator_name": "用户名称",
      "category_id": 1,
      "bbk_ids": [],
      "status": "active",
      "created_at": "ISO8601",
      "updated_at": "ISO8601"
    }
  ]
}
```

字段说明：
- `bbk_ids`：空数组表示对该 source_id 全员可见；非空时表示仅对指定 bbk_id 可见
- `status`：`active` 上架中；`inactive` 已下架
- `version`：语义化版本号（如 `1.0.0`），管理员重复上架同名技能时递增，`updated_at` 同步更新

### 3.2 用户技能 skill.json 扩展字段

在现有 `skill.json` 基础上新增：

```json
{
  "source": "marketplace:{item_id}",
  "distributed_by": "user_id",
  "received_version": "1.0.0"
}
```

分类判断逻辑：
- **我创建的**：`source` 不含 `marketplace:` 前缀
- **我接收的**：`source` 含 `marketplace:` 前缀

版本更新逻辑：
- 用户"我接收的"列表中，若市场条目 `version` 与本地 `received_version` 不一致，展示"有更新"标记
- 用户点击更新后，拉取市场最新版本覆盖本地，`received_version` 同步更新

### 3.3 数据库日志表

#### 用户操作日志

技能和 MCP 共用一张表，通过 `item_type` 区分。

```sql
CREATE TABLE swe_user_item_operation_logs (
  id           BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
  source_id    VARCHAR(64)  NOT NULL COMMENT '应用入口标识',
  user_id      VARCHAR(128) NOT NULL COMMENT '操作用户ID',
  user_name    VARCHAR(256) COMMENT '操作用户名称',
  operation    VARCHAR(32)  NOT NULL COMMENT '操作类型：create/edit/delete',
  item_type    VARCHAR(16)  NOT NULL COMMENT '条目类型：skill/mcp',
  item_name    VARCHAR(256) NOT NULL COMMENT '条目名称',
  created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '操作时间',
  INDEX idx_source_id (source_id),
  INDEX idx_user_id (user_id),
  INDEX idx_item_type (item_type)
) COMMENT='用户技能/MCP操作日志';
```

#### 市场操作日志

```sql
CREATE TABLE swe_marketplace_operation_logs (
  id             BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
  source_id      VARCHAR(64)  NOT NULL COMMENT '应用入口标识',
  operator_id    VARCHAR(64)  NOT NULL COMMENT '操作人用户ID',
  operator_name  VARCHAR(256) COMMENT '操作人用户名称',
  operation      VARCHAR(32)  NOT NULL COMMENT '操作类型：publish/unpublish/distribute',
  item_type      VARCHAR(16)  NOT NULL COMMENT '条目类型：skill/mcp',
  item_id        VARCHAR(64)  NOT NULL COMMENT '市场条目ID',
  item_name      VARCHAR(256) COMMENT '市场条目名称',
  target_user_id VARCHAR(64)  COMMENT '分发目标用户ID',
  target_user_name VARCHAR(256) COMMENT '分发目标用户名称',
  target_bbk_id  VARCHAR(64)  COMMENT '分发目标用户所属机构ID（快照）',
  created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '操作时间',
  INDEX idx_source_id (source_id),
  INDEX idx_item_id (item_id),
  INDEX idx_target_user_id (target_user_id)
) COMMENT='市场操作日志';
```

字段说明：
- `swe_marketplace_operation_logs.operation`：`publish`（上架）/ `unpublish`（下架）/ `distribute`（分发）
- `item_type`：`skill` / `mcp`
- `target_user_id`：分发时展开到用户粒度，每个用户一条记录
- `target_bbk_id`：分发时快照目标用户所属机构，用于机构维度聚合统计

常用查询：
```sql
-- 某技能分发给了多少人
SELECT COUNT(DISTINCT target_user_id) FROM swe_marketplace_operation_logs
WHERE item_id = ? AND operation = 'distribute';

-- 某 bbk_id 下收到了多少技能
SELECT COUNT(DISTINCT item_id) FROM swe_marketplace_operation_logs
WHERE target_bbk_id = ? AND operation = 'distribute';

-- 某用户收到了哪些技能
SELECT * FROM swe_marketplace_operation_logs
WHERE target_user_id = ? AND operation = 'distribute';
```

### 3.4 分类配置表

按 source-id 隔离，暂不提供管理页面，直接操作数据库配置。

```sql
CREATE TABLE swe_marketplace_categories (
  id          BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
  source_id   VARCHAR(64)  NOT NULL COMMENT '应用入口标识',
  name        VARCHAR(128) NOT NULL COMMENT '分类名称',
  sort_order  INT          NOT NULL DEFAULT 0 COMMENT '排序权重，升序',
  created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  INDEX idx_source_id (source_id)
) COMMENT='市场技能分类配置';
```

市场条目通过 `category_id` 关联分类，前端市场列表按分类分组或过滤展示。分类是市场的组织方式，不随技能分发到用户本地，修改分类只影响市场展示，不影响已分发的用户技能。

---

## 四、bbk_id 过滤规则

```python
if user.bbk_id == "100":
    # 总行用户，看该 source_id 下所有技能
    items where source_id == user.source_id
else:
    # 分行用户，看全员可见 + 总行技能 + 本分行技能
    items where source_id == user.source_id
      and (bbk_ids == [] or "100" in bbk_ids or user.bbk_id in bbk_ids)
```

分发时按 bbk_id 展开用户列表，通过 `swe_tenant_init_source` 表查询。该表需新增以下字段：

```sql
ALTER TABLE swe_tenant_init_source
  ADD COLUMN bbk_id    VARCHAR(64)  COMMENT '所属机构ID',
  ADD COLUMN tenant_name VARCHAR(256) COMMENT '用户名称';
```

---

## 五、API 设计

### 权限说明

- 所有接口从请求头读取 `X-Source-Id`
- 管理员操作额外校验 `manager` 标识

### 管理员 API

```
POST   /api/marketplace/skills                          # 上架技能（版本号系统自动从 1.0.0 开始，重复上架自动递增 patch 位）
DELETE /api/marketplace/skills/{item_id}                # 下架技能
POST   /api/marketplace/skills/{item_id}/distribute     # 分发技能
```

分发请求体：
```json
{
  "target_type": "all | bbk_id | user_id",
  "target_values": ["bbk_001", "bbk_002"]
}
```

字段说明：
- `target_type=all`：`target_values` 为空，分发给该 source_id 下所有用户
- `target_type=bbk_id`：`target_values` 为 bbk_id 列表，后端展开为对应用户列表
- `target_type=user_id`：`target_values` 为 user_id 列表，直接分发

分发逻辑：后端根据 `target_type` 展开目标用户列表，逐用户写文件 + 写日志（每用户一条，记录 `target_bbk_id` 快照）。

### 用户 API

```
GET    /api/marketplace/categories              # 获取当前 source-id 下的分类列表
GET    /api/marketplace/skills                  # 浏览市场技能列表（按 source_id + bbk_id 过滤）
GET    /api/marketplace/skills/{item_id}        # 预览技能详情

GET    /api/skills/mine                         # 我创建的技能（新增接口，按 source 字段过滤）
GET    /api/skills/received                     # 我接收的技能（新增接口，按 source 字段过滤）
PUT    /api/skills/{skill_name}                 # 编辑我创建的技能（复用现有接口）
DELETE /api/skills/{skill_name}                 # 删除技能（复用现有接口）
```

---

## 六、前端页面设计

### UI 风格规范

参考 `D:\Vibe Coding\CmbCoworkAgent-main` 项目的应用市场、MCP、技能页面，尽量模仿其 UI 和交互风格，使用 Ant Design 5 + antd-style 实现：

- **布局**：左侧分类树 + 右侧卡片网格，参考 `MarketPanel.tsx`
- **卡片**：`Card` 组件 + `hoverable`，悬停时白色背景 + 阴影过渡（200ms）
- **徽章系统**：`Tag` 组件实现分类标签和状态标记（已安装、有更新等）
- **统计指标**：卡片内渐变背景小块展示调用次数、用户量，参考 `MarketPanel.tsx`
- **颜色**：跟随 CoPaw 现有主题色，不移植 CmbCoworkAgent 的棕色系
- **参考文件**：
  - `D:\Vibe Coding\CmbCoworkAgent-main\src\renderer\src\components\customize\MarketPanel.tsx`
  - `D:\Vibe Coding\CmbCoworkAgent-main\src\renderer\src\components\customize\McpPanel.tsx`
  - `D:\Vibe Coding\CmbCoworkAgent-main\src\renderer\src\components\customize\SkillsPanel.tsx`

### 菜单结构

```
侧边栏
├── 应用市场（所有用户可见）
│   ├── tab: 技能
│   └── tab: MCP（留空占位）
├── 我的技能（所有用户可见）
│   ├── 我创建的
│   └── 我接收的
├── 我的 MCP（所有用户可见，留空占位）
├── Skills（原有菜单，保留不变）
└── MCP（原有菜单，保留不变）
```

### 应用市场 - 技能 tab

共用同一页面，根据 `manager` 标识控制操作按钮显示：

| 操作 | 管理员 | 普通用户 |
|------|--------|----------|
| 浏览列表 | ✓ | ✓ |
| 预览详情 | ✓ | ✓ |
| 上架 | ✓ | - |
| 下架 | ✓ | - |
| 分发 | ✓ | - |
| 编辑 | - | - |

市场技能不支持在市场页编辑，管理员如需修改需通过"我的技能 - 我创建的"编辑后重新同步到市场。

**页面布局**：左侧分类树 + 右侧技能列表
- 左侧：展示当前 source-id 下的分类列表，顶部有"全部"选项，默认选中
- 右侧：默认展示所有技能，选择分类后只展示该分类下的技能

**技能卡片展示字段**：
- 技能名称、描述、分类
- 创建人、版本号、创建时间
- 调用次数（来自 `swe_tracing_spans`，`WHERE event_type='skill_invocation' AND skill_name=?`）
- 用户量（来自 `swe_tracing_spans`，`COUNT(DISTINCT user_id)`）

调用次数和用户量按 `source_id` 隔离统计，通过技能名称关联市场条目（接收的技能不支持重命名，名称唯一）。

**技能详情页**：

点击技能卡片进入详情页，除卡片字段外，额外展示调用客户明细表格：

| 字段 | 说明 |
|------|------|
| 用户ID | `user_id` |
| 用户名称 | `user_name`（来自 tracing 记录） |
| 调用次数 | 该用户对该技能的调用总次数 |

数据来源：`swe_tracing_spans` 表，`WHERE event_type='skill_invocation' AND skill_name=? AND source_id=?`，按 `user_id` 分组聚合，按调用次数降序排列。

**分发弹窗**：多选叠加模式
- 全员：勾选后禁用其他选项
- 按机构：多选下拉，列表从 `console/src/constants/bbk.ts` 静态读取
- 按用户：多选输入，支持搜索 user_id

### 我的技能菜单 - 我创建的

左侧树状列表 + 右侧详情面板：
- 技能内容预览（SKILL.md 渲染）
- 编辑：可修改技能内容和配置，保存后写回文件
- 启用/禁用：切换技能激活状态
- 删除（支持批量删除）
- 上传 ZIP：导入 ZIP 格式技能包（最大 100MB），含冲突重命名处理
- 创建新技能：通过表单填写技能内容和配置
- 同步到市场（仅管理员可见）：将技能上架到应用市场

### 我的技能菜单 - 我接收的

左侧树状列表 + 右侧详情面板：
- 技能内容预览（只读）
- 启用/禁用：切换技能激活状态
- 删除（支持批量删除）
- 有更新标记：市场版本高于本地版本时展示，点击后拉取最新版本覆盖本地
- 无编辑入口

---

## 七、本期范围

| 模块 | 本期 | 留空/后续 |
|------|------|-----------|
| 应用市场 - 技能 tab | 完整实现 | - |
| 应用市场 - MCP tab | 留空占位 | 其他开发人员 |
| 我的技能菜单 | 完整实现 | - |
| 我的 MCP 菜单 | 留空占位 | 其他开发人员 |
| 老 Skills / MCP 菜单 | 保留不变 | - |
| 同步到市场 | 仅管理员可见，我创建的技能支持 | - |
| 历史数据迁移 | - | 后续迭代 |
