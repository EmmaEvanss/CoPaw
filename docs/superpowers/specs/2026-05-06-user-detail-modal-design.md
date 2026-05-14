# 运营看板用户详情弹窗设计

## 概述

在运营看板页面的用户分析模块，热门用户表格中点击用户，弹出 Modal 展示用户详情，包含用户统计信息、会话列表和对话流。

## 需求摘要

| 要素 | 需求 |
|------|------|
| 触发入口 | 运营看板热门用户表格，点击用户行 |
| 弹窗形式 | Modal 模态框 |
| 弹窗宽度 | 800px |
| 布局结构 | 顶部用户统计 + 左侧会话列表 + 右侧对话流 |

## 功能详情

### Modal 布局

```
┌─────────────────────────────────────────────────────────────┐
│  用户详情                                          [X]      │
├─────────────────────────────────────────────────────────────┤
│  用户统计信息（Descriptions + Tag 列表）                     │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────────┐  ┌────────────────────────────────┐ │
│  │ 会话卡片列表      │  │ 对话流/时间线                   │ │
│  │ (280px, 分页)    │  │ (500px, 滚动)                  │ │
│  └──────────────────┘  └────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 顶部：用户统计信息

复用用户分析页面抽屉的展示内容：

1. **基础统计**（Descriptions 2列）
   - 总会话数
   - 总对话数
   - 总 Token
   - 平均时长
   - 输入 Token
   - 输出 Token

2. **使用统计**（Tag 列表）
   - 模型使用：`[model_name: count]`
   - 工具使用：`[tool_name: count]`
   - 技能使用：`[skill_name: count]`

### 左侧：会话卡片列表

**卡片内容：**
- session_id（截断显示）
- 渠道
- 对话数
- Token 消耗
- 活跃时间

**交互：**
- 点击卡片切换选中，选中卡片边框高亮（蓝色）
- 底部分页，默认每页 10 条

### 右侧：对话流/时间线

**展示内容：**
选中会话下所有对话，按时间顺序以 Timeline 形式展示。

**基础信息展示（使用 TraceListItem 数据）：**
- 时间戳
- Token 消耗
- 状态标签（completed/error/running）
- 模型名称
- 技能数（skills_count）
- 工具调用数（从 tools_called 计算或新增字段）

**详情内容展示（需调用 getTraceDetail）：**
- 用户输入（灰色背景区）
- 模型输出（蓝色背景区）
- 技能使用详情：技能名称列表（skills_used）
- 工具调用详情：工具名称、调用次数、耗时、错误信息（tools_called）

**交互与性能策略：**
- 初始加载时只展示基础信息列表（使用 getTraces API）
- 用户点击某条对话后，调用 getTraceDetail 获取详情，展开显示：
  - 用户输入和模型输出
  - 技能使用标签列表
  - 工具调用详情卡片（展示工具名称、耗时、错误等）
- 避免一次性加载所有对话详情造成大量 API 调用
- 支持分页，默认每页 10 条

## 技术设计

### 文件结构

```
console/src/pages/Analytics/BusinessOverview/
├── index.tsx                          # 运营看板主页面（修改）
├── index.module.less                  # 样式（修改）
├── types.ts                           # 类型定义（修改）
└── components/
    └── UserDetailModal/
        ├── index.tsx                  # Modal 容器组件
        ├── index.module.less          # Modal 样式
        ├── UserStatsHeader.tsx        # 顶部用户统计
        ├── SessionCardList.tsx        # 左侧会话卡片列表
        └── SessionTracesFlow.tsx      # 右侧对话流/时间线
```

### 组件职责

| 组件 | 职责 |
|------|------|
| `UserDetailModal` | Modal 容器，管理状态（用户、会话、对话），协调子组件 |
| `UserStatsHeader` | 展示用户统计信息 |
| `SessionCardList` | 展示会话卡片列表，处理分页和选中交互 |
| `SessionTracesFlow` | 展示选中会话下所有对话的对话流 |

### 状态管理

```typescript
interface UserDetailModalState {
  // Modal 状态
  open: boolean;
  userId: string | null;

  // 用户统计
  userStats: UserStats | null;
  userLoading: boolean;

  // 会话列表
  sessions: SessionListItem[];
  sessionsTotal: number;
  sessionsPage: number;
  sessionsPageSize: number;
  sessionsLoading: boolean;

  // 对话流
  selectedSessionId: string | null;
  traces: TraceListItem[];
  tracesTotal: number;
  tracesPage: number;
  tracesPageSize: number;
  tracesLoading: boolean;
}
```

### API 调用

| 场景 | API | 参数 |
|------|-----|------|
| 打开 Modal | `tracingApi.getUserStats(userId)` | 用户 ID |
| 加载会话列表 | `tracingApi.getSessions(page, pageSize, { user_id })` | 用户 ID、分页 |
| 加载对话列表 | `tracingApi.getTraces(page, pageSize, { session_id })` | 会话 ID、分页 |
| 加载对话详情 | `tracingApi.getTraceDetail(traceId)` | 对话 ID（点击对话时调用） |

### 数据流

1. 用户点击热门用户表格行 → 打开 Modal，传入 userId
2. Modal 打开后调用 `getUserStats` 获取用户统计
3. 同时调用 `getSessions` 获取会话列表
4. 默认选中第一个会话，调用 `getTraces` 获取对话列表
5. 用户切换会话 → 更新 selectedSessionId，重新加载对话列表
6. 用户关闭 Modal → 重置所有状态

## 样式规范

### Modal 样式

```less
.userDetailModal {
  :global(.ant-modal-body) {
    padding: 16px;
  }
}

.modalContent {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 70vh;
}

.topSection {
  flex-shrink: 0;
}

.bottomSection {
  display: flex;
  gap: 16px;
  flex: 1;
  min-height: 0;
}

.leftPanel {
  width: 280px;
  flex-shrink: 0;
  overflow-y: auto;
}

.rightPanel {
  flex: 1;
  overflow-y: auto;
}
```

### 会话卡片样式

```less
.sessionCard {
  padding: 12px;
  border: 1px solid #e8e8e8;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 8px;

  &:hover {
    border-color: #1890ff;
  }

  &.selected {
    border-color: #1890ff;
    background: #e6f7ff;
  }
}
```

### 对话流样式

```less
.traceItem {
  padding: 12px;
  border-radius: 6px;
  margin-bottom: 12px;
}

.userMessage {
  background: #f5f5f5;
  padding: 12px;
  border-radius: 6px;
  margin: 8px 0;
}

.modelOutput {
  background: #e6f7ff;
  padding: 12px;
  border-radius: 6px;
  margin: 8px 0;
}

.traceHeader {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.traceExpandBtn {
  cursor: pointer;
  color: #1890ff;
  font-size: 12px;
}

.skillsList {
  margin: 8px 0;
}

.toolCard {
  background: #fafafa;
  padding: 8px 12px;
  border-radius: 4px;
  margin: 4px 0;
}
```

## 实现计划

1. **创建组件文件结构**
   - 创建 `components/UserDetailModal/` 目录
   - 创建各子组件文件

2. **实现 UserDetailModal 容器**
   - Modal 基础结构
   - 状态管理逻辑
   - API 调用封装

3. **实现 UserStatsHeader**
   - 复用用户分析抽屉的展示逻辑
   - Descriptions + Tag 列表布局

4. **实现 SessionCardList**
   - 卡片列表渲染
   - 选中状态管理
   - 分页组件

5. **实现 SessionTracesFlow**
   - Timeline 组件渲染
   - 对话内容展示
   - 加载更多/分页

6. **集成到运营看板**
   - 修改 BusinessOverview/index.tsx
   - 添加用户行点击事件
   - 引入 UserDetailModal 组件

## 验收标准

- [ ] 点击热门用户表格行，Modal 正确打开
- [ ] 用户统计信息正确展示
- [ ] 会话列表正确加载，支持分页
- [ ] 点击会话卡片切换选中状态
- [ ] 对话流正确展示选中会话的对话列表（基础信息）
- [ ] 点击对话展开显示用户输入和模型输出
- [ ] 技能使用数量在列表中正确显示，详情中展示技能名称列表
- [ ] 工具调用数量在列表中正确显示，详情中展示工具调用卡片（名称、耗时、错误）
- [ ] 关闭 Modal 后状态正确重置
