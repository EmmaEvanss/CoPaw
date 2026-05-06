# 技能菜单功能迁移实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 src/swe 中的用户技能管理功能迁移到 market 服务，统一用户技能管理入口，减少功能重叠。

**Architecture:**
- Market 服务负责用户技能 CRUD（创建、删除、启用/禁用、文件编辑）
- SWE 服务保留运行时支持（技能列表查询、技能池管理、Hub 导入）
- 通过 HTTP 回调机制保持数据同步

**Tech Stack:** Python 3.12, FastAPI, React, TypeScript, pytest

---

## 文件结构总览

### 新增文件

| 文件 | 说明 |
|------|------|
| `console/src/components/RedirectToMySkills/index.tsx` | 引导跳转组件 |

### 修改文件

| 文件 | 修改内容 |
|------|----------|
| `console/src/pages/Agent/Skills/index.tsx` | 移除 CRUD 功能，改为只读视图 |
| `console/src/pages/Agent/Skills/useSkills.ts` | 移除 createSkill, uploadSkill, toggleEnabled, deleteSkill |
| `console/src/api/modules/skill.ts` | 移除 CRUD 相关 API 方法 |
| `console/src/layouts/MainLayout/index.tsx` | 调整侧边栏导航 |

### 删除文件

| 文件 | 说明 |
|------|------|
| `src/swe/app/routers/skills.py` 中的部分端点 | 移除迁移到 Market 的端点 |

---

## Phase 1: 前端改造（只读化工作空间技能页面）

### Task 1.1: 创建引导跳转组件

**Files:**
- Create: `console/src/components/RedirectToMySkills/index.tsx`

- [ ] **Step 1: 创建引导跳转组件**

```tsx
// console/src/components/RedirectToMySkills/index.tsx
import { Button, Space, Typography } from "antd";
import { Navigate, useLocation } from "react-router-dom";
import { FolderOutlined, RightOutlined } from "@ant-design/icons";
import { useTranslation } from "react-i18next";

const { Text, Title } = Typography;

interface RedirectToMySkillsProps {
  feature: "create" | "edit" | "delete" | "enable-disable" | "upload";
}

export function RedirectToMySkills({ feature }: RedirectToMySkillsProps) {
  const { t } = useTranslation();
  const location = useLocation();

  const featureMessages: Record<string, { title: string; description: string }> = {
    create: {
      title: t("skills.redirectCreateTitle", "创建技能"),
      description: t("skills.redirectCreateDesc", "技能创建功能已迁移到「我的技能」页面"),
    },
    edit: {
      title: t("skills.redirectEditTitle", "编辑技能"),
      description: t("skills.redirectEditDesc", "技能编辑功能已迁移到「我的技能」页面"),
    },
    delete: {
      title: t("skills.redirectDeleteTitle", "删除技能"),
      description: t("skills.redirectDeleteDesc", "技能删除功能已迁移到「我的技能」页面"),
    },
    "enable-disable": {
      title: t("skills.redirectToggleTitle", "启用/禁用技能"),
      description: t("skills.redirectToggleDesc", "技能启用/禁用功能已迁移到「我的技能」页面"),
    },
    upload: {
      title: t("skills.redirectUploadTitle", "上传技能"),
      description: t("skills.redirectUploadDesc", "技能上传功能已迁移到「我的技能」页面"),
    },
  };

  const { title, description } = featureMessages[feature] || featureMessages.create;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        height: "100%",
        padding: 48,
        textAlign: "center",
      }}
    >
      <FolderOutlined style={{ fontSize: 48, color: "#1890ff", marginBottom: 24 }} />
      <Title level={4} style={{ marginBottom: 8 }}>
        {title}
      </Title>
      <Text type="secondary" style={{ marginBottom: 24 }}>
        {description}
      </Text>
      <Space>
        <Button type="primary" icon={<RightOutlined />} href="/my-skills">
          {t("skills.goToMySkills", "前往我的技能")}
        </Button>
      </Space>
    </div>
  );
}

export default RedirectToMySkills;
```

- [ ] **Step 2: 导出组件**

在 `console/src/components/index.ts` 中添加导出（如果存在）或跳过此步骤。

---

### Task 1.2: 改造 useSkills Hook（移除 CRUD 功能）

**Files:**
- Modify: `console/src/pages/Agent/Skills/useSkills.ts`

- [ ] **Step 1: 移除 createSkill 函数**

将 `createSkill` 函数替换为空实现或直接删除。修改后的 `useSkills.ts` 应移除第 97-118 行的 `createSkill` 函数。

```tsx
// 移除 createSkill 函数（第 97-118 行）
// 移除后 useSkills 返回值中不再包含 createSkill
```

- [ ] **Step 2: 移除 uploadSkill 函数**

移除第 120-158 行的 `uploadSkill` 函数。

```tsx
// 移除 uploadSkill 函数（第 120-158 行）
// 移除后 useSkills 返回值中不再包含 uploadSkill
```

- [ ] **Step 3: 移除 toggleEnabled 函数**

移除第 262-288 行的 `toggleEnabled` 函数。

```tsx
// 移除 toggleEnabled 函数（第 262-288 行）
// 移除后 useSkills 返回值中不再包含 toggleEnabled
```

- [ ] **Step 4: 移除 deleteSkill 函数**

移除第 290-318 行的 `deleteSkill` 函数。

```tsx
// 移除 deleteSkill 函数（第 290-318 行）
// 移除后 useSkills 返回值中不再包含 deleteSkill
```

- [ ] **Step 5: 更新返回值**

修改第 320-334 行的返回语句，移除已删除的函数：

```tsx
return {
  skills,
  loading,
  importing,
  importFromHub,
  cancelImport,
  refreshSkills: fetchSkills,
  hardRefresh,
};
```

- [ ] **Step 6: 移除 uploading 状态**

移除第 35 行的 `uploading` 状态：

```tsx
// 移除: const [uploading, setUploading] = useState(false);
```

- [ ] **Step 7: 验证 TypeScript 编译通过**

```bash
cd console && npm run typecheck
```

Expected: 无编译错误

---

### Task 1.3: 改造 Skills 页面组件

**Files:**
- Modify: `console/src/pages/Agent/Skills/index.tsx`

- [ ] **Step 1: 移除 CRUD 相关导入和状态**

修改第 1-35 行的导入部分，移除不再需要的导入：

```tsx
import { useEffect, useRef, useState } from "react";
import { Button, Form, Modal, Tooltip } from "@agentscope-ai/design";
import {
  CloseOutlined,
  DownloadOutlined,
  ImportOutlined,
  ReloadOutlined,
  SwapOutlined,
} from "@ant-design/icons";
import type { PoolSkillSpec, SkillSpec } from "../../../api/types";
import {
  SkillCard,
  ImportHubModal,
  PoolTransferModal,
} from "./components";
import { useSkills } from "./useSkills";
import { useTranslation } from "react-i18next";
import { useAgentStore } from "../../../stores/agentStore";
import { useAppMessage } from "../../../hooks/useAppMessage";
import api from "../../../api";
import { invalidateSkillCache } from "../../../api/modules/skill";
import { parseErrorDetail } from "../../../utils/error";
import { PageHeader } from "@/components/PageHeader";
import styles from "./index.module.less";
```

注意：移除了 `DeleteOutlined`, `PlusOutlined`, `UploadOutlined` 图标和部分组件导入。

- [ ] **Step 2: 移除 fileInputRef 和相关上传逻辑**

移除第 59 行的 `fileInputRef`，以及第 98-148 行的 `handleUploadClick` 和 `handleFileChange` 函数。

- [ ] **Step 3: 移除创建技能相关逻辑**

移除第 150-158 行的 `handleCreate` 函数，以及第 54 行的 `drawerOpen` 状态、第 56 行的 `editingSkill` 状态、第 58 行的 `form`。

- [ ] **Step 4: 移除编辑技能相关逻辑**

移除第 196-206 行的 `handleEdit` 函数，以及第 220-223 行的 `handleDrawerClose` 函数。

- [ ] **Step 5: 移除启用/禁用和删除逻辑**

移除第 208-218 行的 `handleToggleEnabled` 和 `handleDelete` 函数。

- [ ] **Step 6: 移除批量删除逻辑**

移除第 414-458 行的 `handleBatchDelete` 函数，以及第 66-80 行的选择相关状态和函数。

- [ ] **Step 7: 简化页面渲染逻辑**

将第 467-676 行的 JSX 简化为只读视图：

```tsx
return (
  <div className={styles.skillsPage}>
    <PageHeader
      items={[{ title: t("nav.agent") }, { title: t("skills.title") }]}
      extra={
        <div className={styles.headerRight}>
          <div className={styles.headerActionsLeft}>
            <Tooltip title={t("skills.refreshHint")}>
              <Button
                type="default"
                icon={<ReloadOutlined spin={loading} />}
                onClick={hardRefresh}
                disabled={loading}
              />
            </Tooltip>
            <Tooltip title={t("skills.downloadFromPoolHint")}>
              <Button
                type="default"
                className={styles.primaryTransferButton}
                onClick={() => setPoolModal("download")}
                icon={<DownloadOutlined />}
              >
                {t("skills.downloadFromPool")}
              </Button>
            </Tooltip>
          </div>
          <div className={styles.headerActionsRight}>
            <Tooltip title={t("skills.importHubHint")}>
              <Button
                type="default"
                onClick={() => setImportModalOpen(true)}
                icon={<ImportOutlined />}
              >
                {t("skills.importHub")}
              </Button>
            </Tooltip>
            <Tooltip title={t("skills.goToMySkillsHint", "管理我的技能")}>
              <Button
                type="primary"
                href="/my-skills"
                icon={<SwapOutlined />}
              >
                {t("skills.goToMySkills", "我的技能")}
              </Button>
            </Tooltip>
          </div>
        </div>
      }
    />

    <ImportHubModal
      open={importModalOpen}
      importing={importing}
      onCancel={closeImportModal}
      onConfirm={handleConfirmImport}
      cancelImport={cancelImport}
      hint="External hub import is separate from the local Skill Pool."
    />

    {loading ? (
      <div className={styles.loading}>
        <span className={styles.loadingText}>{t("common.loading")}</span>
      </div>
    ) : skills.length === 0 ? (
      <div className={styles.emptyState}>
        <div className={styles.emptyStateBadge}>
          {t("skills.emptyStateBadge")}
        </div>
        <h2 className={styles.emptyStateTitle}>
          {t("skills.emptyStateTitle")}
        </h2>
        <p className={styles.emptyStateText}>{t("skills.emptyStateText")}</p>
        <div className={styles.emptyStateActions}>
          <Button
            type="default"
            className={styles.primaryTransferButton}
            onClick={() => setPoolModal("download")}
            icon={<DownloadOutlined />}
          >
            {t("skills.emptyStateDownload")}
          </Button>
          <Button
            type="primary"
            href="/my-skills"
          >
            {t("skills.goToMySkills", "我的技能")}
          </Button>
        </div>
      </div>
    ) : (
      <div className={styles.skillsGrid}>
        {skills
          .slice()
          .sort((a, b) => {
            if (a.enabled && !b.enabled) return -1;
            if (!a.enabled && b.enabled) return 1;
            return a.name.localeCompare(b.name);
          })
          .map((skill) => (
            <SkillCard
              key={skill.name}
              skill={skill}
              onClick={() => {
                // 只读模式，点击跳转到我的技能页面
                window.location.href = "/my-skills";
              }}
              readOnly={true}
            />
          ))}
      </div>
    )}

    <PoolTransferModal
      mode={poolModal}
      skills={skills}
      poolSkills={poolSkills}
      onCancel={closePoolModal}
      onUpload={() => {}}
      onDownload={handleDownloadFromPool}
    />
  </div>
);
```

- [ ] **Step 8: 移除 SkillDrawer 和 conflictRenameModal**

移除第 669-675 行的 `SkillDrawer` 组件渲染和 `conflictRenameModal`。

- [ ] **Step 9: 验证 TypeScript 编译通过**

```bash
cd console && npm run typecheck
```

Expected: 无编译错误

---

### Task 1.4: 修改 SkillCard 组件支持只读模式

**Files:**
- Modify: `console/src/pages/Agent/Skills/components/SkillCard.tsx`

- [ ] **Step 1: 添加 readOnly prop**

修改 SkillCard 组件接口，添加 `readOnly` 属性：

```tsx
interface SkillCardProps {
  skill: SkillSpec;
  isHover?: boolean;
  selected?: boolean;
  onSelect?: () => void;
  onClick: () => void;
  onMouseEnter?: () => void;
  onMouseLeave?: () => void;
  onToggleEnabled?: (e: React.MouseEvent) => void;
  onDelete?: (e: React.MouseEvent) => void;
  readOnly?: boolean;
}
```

- [ ] **Step 2: 条件渲染操作按钮**

在渲染删除和启用/禁用按钮时，添加 `readOnly` 判断：

```tsx
{!readOnly && (
  <>
    <Button
      type="text"
      size="small"
      icon={skill.enabled ? <StopOutlined /> : <CheckCircleOutlined />}
      onClick={(e) => onToggleEnabled?.(e)}
    >
      {skill.enabled ? "禁用" : "启用"}
    </Button>
    <Button
      type="text"
      size="small"
      danger
      icon={<DeleteOutlined />}
      onClick={(e) => onDelete?.(e)}
    >
      删除
    </Button>
  </>
)}
```

- [ ] **Step 3: 添加只读提示**

当 `readOnly` 为 true 时，鼠标悬停显示提示：

```tsx
<Tooltip title={readOnly ? "前往「我的技能」管理" : undefined}>
  <div className={styles.skillCard} onClick={onClick}>
    {/* card content */}
  </div>
</Tooltip>
```

---

### Task 1.5: 清理 API 模块

**Files:**
- Modify: `console/src/api/modules/skill.ts`

- [ ] **Step 1: 移除 createSkill 方法**

移除第 197-211 行的 `createSkill` 方法：

```tsx
// 移除:
// createSkill: (skillName, content, config, enable) => ...
```

- [ ] **Step 2: 移除 saveSkill 方法**

移除第 213-226 行的 `saveSkill` 方法。

- [ ] **Step 3: 移除 enableSkill 方法**

移除第 253-256 行的 `enableSkill` 方法。

- [ ] **Step 4: 移除 disableSkill 方法**

移除第 258-261 行的 `disableSkill` 方法。

- [ ] **Step 5: 移除 batchEnableSkills 方法**

移除第 263-267 行的 `batchEnableSkills` 方法。

- [ ] **Step 6: 移除 batchDeleteSkills 方法**

移除第 269-276 行的 `batchDeleteSkills` 方法。

- [ ] **Step 7: 移除 deleteSkill 方法**

移除第 285-289 行的 `deleteSkill` 方法。

- [ ] **Step 8: 移除 uploadSkill 方法**

移除第 513-531 行的 `uploadSkill` 方法。

- [ ] **Step 9: 验证 TypeScript 编译通过**

```bash
cd console && npm run typecheck
```

Expected: 无编译错误

---

### Task 1.6: 调整侧边栏导航

**Files:**
- Modify: `console/src/layouts/MainLayout/index.tsx` 或 `console/src/layouts/Sidebar.tsx`

- [ ] **Step 1: 添加「我的技能」菜单项**

在侧边栏顶部或「工作空间」分组前添加「我的技能」入口：

```tsx
const menuItems = [
  {
    key: "my-skills",
    icon: <FolderOutlined />,
    label: t("nav.mySkills", "我的技能"),
    path: "/my-skills",
  },
  // ... 其他菜单项
];
```

- [ ] **Step 2: 验证导航功能正常**

```bash
cd console && npm run dev
```

手动测试：
1. 点击侧边栏「我的技能」跳转到 `/my-skills`
2. 点击侧边栏「技能管理」跳转到 `/agent/skills`

---

## Phase 2: 后端清理

### Task 2.1: 标记 SWE 服务冗余端点为废弃

**Files:**
- Modify: `src/swe/app/routers/skills.py`

- [ ] **Step 1: 添加废弃警告**

为即将废弃的端点添加 `DeprecationWarning` 日志：

```python
import warnings

@router.post("", deprecated=True)
async def create_skill(request: Request, body: CreateSkillRequest):
    warnings.warn(
        "POST /skills is deprecated. Use Market API POST /market/skills/upload instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    # 保留原有实现，但标记为废弃
    ...
```

对以下端点执行相同操作：
- `POST /skills` (create_skill)
- `POST /skills/upload` (upload_skill_zip)
- `PUT /skills/save` (save_workspace_skill)
- `DELETE /skills/{skill_name}` (delete_skill)
- `POST /skills/{skill_name}/enable` (enable_skill)
- `POST /skills/{skill_name}/disable` (disable_skill)
- `POST /skills/batch-enable` (batch_enable_skills)
- `POST /skills/batch-disable` (batch_disable_skills)
- `POST /skills/batch-delete` (batch_delete_skills)

- [ ] **Step 2: 添加 FastAPI deprecated 标记**

使用 FastAPI 的 `deprecated` 参数：

```python
@router.post(
    "",
    deprecated=True,
    description="Deprecated: Use Market API POST /market/skills/upload instead.",
)
async def create_skill(...):
    ...
```

---

### Task 2.2: 更新路由注册

**Files:**
- Modify: `src/swe/app/routers/__init__.py`

- [ ] **Step 1: 确认 internal 路由已注册**

验证 `internal.py` 路由已正确注册：

```python
from .internal import router as internal_router

# 在路由注册部分
app.include_router(internal_router, prefix="/api")
```

---

## Phase 3: 测试验证

### Task 3.1: 验证 Market 服务功能完整性

- [ ] **Step 1: 运行 Market 服务测试**

```bash
cd /path/to/project
venv/bin/python -m pytest tests/unit/market/ -v
```

Expected: 所有测试通过

- [ ] **Step 2: 手动测试 Market API**

使用 curl 或 Postman 测试以下端点：

```bash
# 获取我的技能列表
curl -X GET "http://localhost:8001/market/skills/mine" \
  -H "X-Source-Id: default" \
  -H "X-User-Id: test_user"

# 启用技能
curl -X POST "http://localhost:8001/market/skills/mine/test_skill/enable" \
  -H "X-Source-Id: default" \
  -H "X-User-Id: test_user"
```

---

### Task 3.2: 验证前端功能

- [ ] **Step 1: 启动前端开发服务器**

```bash
cd console && npm run dev
```

- [ ] **Step 2: 测试「我的技能」页面**

1. 导航到 `/my-skills`
2. 测试上传技能功能
3. 测试启用/禁用技能功能
4. 测试删除技能功能
5. 测试文件编辑功能

- [ ] **Step 3: 测试「工作空间技能」页面**

1. 导航到 `/agent/skills`
2. 验证只能查看技能列表
3. 验证「从池下载」功能正常
4. 验证「Hub 导入」功能正常
5. 验证点击「我的技能」按钮跳转正确

---

### Task 3.3: 端到端测试

- [ ] **Step 1: 完整流程测试**

1. 在 `/my-skills` 创建新技能
2. 在 `/agent/skills` 验证技能已同步显示
3. 在 `/my-skills` 禁用技能
4. 在 `/agent/skills` 验证状态已更新
5. 在 `/my-skills` 删除技能
6. 在 `/agent/skills` 验证技能已移除

- [ ] **Step 2: 验证 Agent 重载**

1. 启用/禁用技能后检查日志
2. 确认 `_trigger_agent_reload` 被调用
3. 确认 Agent 重新加载配置

---

### Task 3.4: 回归测试

- [ ] **Step 1: 运行完整测试套件**

```bash
venv/bin/python -m pytest tests/ -v --tb=short
```

Expected: 所有测试通过

- [ ] **Step 2: 验证 API 兼容性**

确保废弃的 SWE API 端点仍可调用（向后兼容）：

```bash
# 测试废弃端点仍可用
curl -X POST "http://localhost:8000/api/skills/test_skill/enable" \
  -H "X-Agent-Id: default"
```

---

## Phase 4: 文档更新

### Task 4.1: 更新 API 文档

- [ ] **Step 1: 更新 OpenAPI 描述**

在 `src/swe/app/routers/skills.py` 中为废弃端点添加说明：

```python
"""
## Deprecated Endpoints (迁移到 Market 服务)

以下端点已废弃，请使用 Market 服务 API：

| 废弃端点 | 替代端点 |
|----------|----------|
| POST /skills | POST /market/skills/upload |
| DELETE /skills/{name} | DELETE /market/skills/mine/{name} |
| POST /skills/{name}/enable | POST /market/skills/mine/{name}/enable |
| POST /skills/{name}/disable | POST /market/skills/mine/{name}/disable |

迁移指南：https://docs.example.com/skill-migration
"""
```

---

### Task 4.2: 更新用户文档

- [ ] **Step 1: 更新 CLAUDE.md**

在 `CLAUDE.md` 的「功能索引」部分添加迁移说明：

```markdown
### 技能管理

| 功能 | API 端点 | 服务 |
|------|----------|------|
| 用户技能 CRUD | /market/skills/* | market |
| 工作空间技能列表 | /skills | src/swe |
| 技能池管理 | /skills/pool/* | src/swe |
| Hub 导入 | /skills/hub/* | src/swe |
```

---

## 回滚方案

如果迁移出现问题，可按以下步骤回滚：

1. **恢复前端代码**
   ```bash
   git revert HEAD~N  # N 为提交数量
   ```

2. **恢复后端代码**
   ```bash
   git revert HEAD~M  # M 为提交数量
   ```

3. **重新部署服务**

---

## 完成检查清单

- [ ] 前端编译无错误
- [ ] 后端测试全部通过
- [ ] 「我的技能」页面功能正常
- [ ] 「工作空间技能」页面只读模式正常
- [ ] Agent 重载回调正常工作
- [ ] API 废弃警告正常显示
- [ ] 文档已更新
