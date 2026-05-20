# BusinessOverview 日期选择联动优化设计

## 背景

当前 BusinessOverview 页面（`console/src/pages/Analytics/BusinessOverview/index.tsx`）的日期选择需要分别选择开始日期和结束日期，用户体验不够流畅。用户希望优化为联动选择，减少操作步骤。

## 目标

将两个独立的 DatePicker 替换为 Ant Design RangePicker，实现日期范围的联动选择，同时保留快捷按钮（今天/近7天/近30天）的便捷功能。

## 设计方案

### 1. UI 布局变更

**改动位置**：第 843-862 行的日期选择区域

**当前布局**：
```
[今天][近7天][近30天]  [开始日期 DatePicker] ~ [结束日期 DatePicker]
```

**新布局**：
```
[今天][近7天][近30天]  [RangePicker 选择日期范围]
```

使用 Ant Design 的 `<DatePicker.RangePicker />`，保持与项目现有风格一致。

### 2. 联动逻辑

**快捷按钮 → RangePicker 联动**：

| 按钮 | RangePicker 填充值 |
|------|-------------------|
| 今天 | `[今天, 今天]` |
| 近7天 | `[今天-6天, 今天]` |
| 近30天 | `[今天-29天, 今天]` |

点击快捷按钮后，RangePicker 自动更新为对应范围，按钮保持选中状态。

**RangePicker 手动选择 → 按钮状态**：

- 用户在 RangePicker 内手动选择日期后，检测是否匹配快捷按钮的范围
- 匹配 → 自动选中对应按钮
- 不匹配 → 取消所有按钮选中状态（即"自定义"模式）

**禁用逻辑**：
- 日期不可选择未来日期（保留当前逻辑）

### 3. 状态管理变更

**移除的状态**：
- `startDate` — 不再单独管理开始日期
- `endDate` — 不再单独管理结束日期

**新增的状态**：
- `dateRange: [Dayjs, Dayjs]` — RangePicker 的日期范围值

**保留的状态**：
- `timeRange: TimeRange` — 快捷按钮的选中状态（"day" | "week" | "month" | "custom"）

**派生值**：
```typescript
const startDateText = dateRange[0].format("YYYY-MM-DD");
const endDateText = dateRange[1].format("YYYY-MM-DD");
```

**状态流转示例**：
1. 用户点击"近7天" → `timeRange = "week"` + `dateRange = [今天-6天, 今天]`
2. 用户在 RangePicker 选择 `[2026-05-10, 2026-05-15]` →
   - 检测不匹配快捷按钮 → `timeRange = "custom"` + `dateRange = [2026-05-10, 2026-05-15]`

### 4. 组件变更范围

**涉及文件**：
- `console/src/pages/Analytics/BusinessOverview/index.tsx` — 主要改动
- `console/src/pages/Analytics/BusinessOverview/index.module.less` — 可能需要调整样式

**改动内容**：

| 改动项 | 说明 |
|--------|------|
| 导入 | 移除单个 DatePicker，导入 RangePicker |
| 状态 | 移除 startDate/endDate，新增 dateRange |
| 函数 | 移除 handleStartDateChange/handleEndDateChange，新增 handleDateRangeChange |
| 禁用逻辑 | 移除 disabledStartDate/disabledEndDate，新增 disabledDate 函数 |
| 渲染 | 替换两个 DatePicker 为一个 RangePicker |

**API 调用**：保持不变，startDateText/endDateText 从 dateRange 派生。

### 5. 错误处理与测试

**错误处理**：
- 用户选择未来日期 → RangePicker 内置禁用逻辑阻止选择
- 用户选择无效范围 → RangePicker 内置逻辑阻止
- API 请求失败 → 保持现有错误提示逻辑

**测试要点**：

| 测试场景 | 验证内容 |
|----------|----------|
| 点击快捷按钮 | RangePicker 值正确更新，按钮状态正确 |
| RangePicker 选择匹配快捷按钮的范围 | 自动选中对应按钮 |
| RangePicker 选择不匹配范围 | 按钮状态变为"自定义" |
| 选择未来日期 | 被禁用，无法选择 |
| API 调用 | startDateText/endDateText 正确传递给 API |
| 初始加载 | 默认显示"今天"按钮选中 + RangePicker 值为今天 |

## 实现状态

已完成。Commit: 03a228d0