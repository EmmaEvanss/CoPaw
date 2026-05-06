# 技能同步到市场与下架功能设计

## 概述

实现两个功能：
1. 我的技能页面 - "同步到市场"按钮：将用户自建技能发布到应用市场
2. 应用市场页面 - "下架技能"按钮：管理员删除已上架的技能

同时删除两个未使用的遗留组件文件。

---

## 一、同步到市场功能

### 1.1 入口位置

- **页面**：我的技能 (`console/src/pages/MySkills/index.tsx`)
- **位置**：技能详情面板（`SkillDetailPanel`）的操作按钮区域
- **可见性**：仅管理员可见（`isManager === true`）
- **条件**：仅对"我创建的"技能显示（`skill.is_received === false`）

### 1.2 交互流程

1. 用户点击"同步到市场"按钮
2. 前端读取技能目录中的文件：
   - `skill.json`：获取技能名称、描述、版本等元数据
   - `SKILL.md`：获取技能说明文档
3. 弹出 Modal 对话框：
   - 名称（预填，不可编辑）
   - 描述（预填，可编辑）
   - 分类（下拉选择，必选）
   - 可见机构（多选，不选则全员可见）
4. 用户点击"上架"按钮
5. 调用 `marketApi.publishSkill()` API
6. 成功后提示"上架成功"，关闭 Modal，刷新技能列表

### 1.3 API 复用

复用现有 `marketApi.publishSkill()` 方法，参数：

```typescript
interface PublishSkillRequest {
  name: string;
  description: string;
  creator_id: string;
  creator_name: string;
  category_id?: number;
  bbk_ids?: string[];
  skill_json: Record<string, unknown>;
  skill_md?: string;
}
```

### 1.4 组件设计

修改现有 `PublishModal` 组件，支持两种模式：

```typescript
interface PublishModalProps {
  open: boolean;
  sourceId: string;
  userId: string;
  userName: string;
  onClose: () => void;
  onSuccess: () => void;
  // 新增：同步模式，传入技能初始数据
  initialData?: {
    skillName: string;
    description: string;
    skillJson: Record<string, unknown>;
    skillMd: string;
  };
}
```

---

## 二、下架技能功能

### 2.1 入口位置

两处入口，均仅管理员可见：

1. **技能卡片** (`SkillCard.tsx`)
   - 在"详情"按钮旁添加"下架"按钮
   - 点击触发确认对话框

2. **技能详情抽屉** (`SkillDetailDrawer.tsx`)
   - 在底部操作区添加"下架"按钮
   - 点击触发确认对话框

### 2.2 交互流程

1. 用户点击"下架"按钮
2. 弹出确认对话框：`确定下架技能「{技能名称}」？下架后用户将无法查看。`
3. 用户点击"确定"
4. 调用 `marketApi.unpublishSkill(sourceId, itemId, userId, userName)`
5. 成功后刷新技能列表，提示"下架成功"

### 2.3 API 复用

复用现有 `marketApi.unpublishSkill()` 方法：

```typescript
unpublishSkill: async (
  sourceId: string,
  itemId: string,
  userId: string,
  userName: string
): Promise<void>
```

---

## 三、删除遗留文件

删除以下未使用的组件文件：

- `console/src/pages/MySkills/CreatedSkills.tsx`
- `console/src/pages/MySkills/ReceivedSkills.tsx`

这两个文件是开发过程中的中间产物，功能按钮只显示占位提示，从未被主页面引用。

---

## 四、文件变更清单

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `console/src/pages/MySkills/index.tsx` | 修改 | 添加"同步到市场"按钮和交互逻辑 |
| `console/src/pages/Market/PublishModal.tsx` | 修改 | 支持 initialData 参数，预填数据 |
| `console/src/pages/Market/SkillCard.tsx` | 修改 | 添加"下架"按钮 |
| `console/src/pages/Market/SkillDetailDrawer.tsx` | 修改 | 添加"下架"按钮 |
| `console/src/pages/MySkills/CreatedSkills.tsx` | 删除 | 遗留文件，未使用 |
| `console/src/pages/MySkills/ReceivedSkills.tsx` | 删除 | 遗留文件，未使用 |

---

## 五、测试要点

1. **同步到市场**
   - 非管理员不可见按钮
   - 接收的技能不显示按钮
   - Modal 正确预填技能名称和描述
   - 分类选择正常工作
   - 上架成功后刷新列表

2. **下架技能**
   - 非管理员不可见按钮
   - 卡片和抽屉的下架按钮功能一致
   - 确认对话框正确显示技能名称
   - 下架成功后刷新列表
