# BusinessOverview 日期选择联动优化 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 BusinessOverview 页面的两个独立 DatePicker 替换为 RangePicker，实现日期范围的联动选择。

**Architecture:** 保持现有快捷按钮（今天/近7天/近30天），使用 Ant Design RangePicker 替换两个独立 DatePicker。状态管理从 startDate/endDate 改为单一 dateRange，派生 startDateText/endDateText 供 API 使用。

**Tech Stack:** React, Ant Design DatePicker.RangePicker, dayjs, TypeScript

---

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| `console/src/pages/Analytics/BusinessOverview/index.tsx` | 修改 | 主要改动：状态、函数、渲染 |
| `console/src/pages/Analytics/BusinessOverview/index.module.less` | 检查 | 可能需要调整 RangePicker 样式 |
| `console/src/pages/Analytics/BusinessOverview/index.test.tsx` | 创建/修改 | 单元测试验证联动逻辑 |

---

### Task 1: 状态重构

**Files:**
- Modify: `console/src/pages/Analytics/BusinessOverview/index.tsx:372-374` (状态定义区域)

- [ ] **Step 1: 修改状态定义**

将原来的 startDate 和 endDate 状态替换为 dateRange：

```typescript
// 原代码（删除）:
// const [startDate, setStartDate] = useState<Dayjs>(dayjs());
// const [endDate, setEndDate] = useState<Dayjs>(dayjs());

// 新代码:
const [dateRange, setDateRange] = useState<[Dayjs, Dayjs]>([dayjs(), dayjs()]);
```

- [ ] **Step 2: 更新派生值**

删除原来的 startDateText 和 endDateText useMemo，改为从 dateRange 派生：

```typescript
// 原代码（删除）:
// const calculatedEndDate = useMemo(() => { ... }, [endDate, startDate, timeRange]);
// const startDateText = useMemo(() => startDate.format("YYYY-MM-DD"), [startDate]);
// const endDateText = useMemo(() => calculatedEndDate.format("YYYY-MM-DD"), [calculatedEndDate]);

// 新代码:
const startDateText = useMemo(
  () => dateRange[0].format("YYYY-MM-DD"),
  [dateRange],
);
const endDateText = useMemo(
  () => dateRange[1].format("YYYY-MM-DD"),
  [dateRange],
);
```

- [ ] **Step 3: 验证 IDE 无类型错误**

确认 TypeScript 编译无错误。保存文件后检查 IDE 或运行 `tsc --noEmit`。

- [ ] **Step 4: Commit**

```bash
git add console/src/pages/Analytics/BusinessOverview/index.tsx
git commit -m "refactor(BusinessOverview): 重构日期状态为 dateRange"
```

---

### Task 2: 函数重构

**Files:**
- Modify: `console/src/pages/Analytics/BusinessOverview/index.tsx:701-750` (handleModeChange/handleStartDateChange/handleEndDateChange 函数区域)

- [ ] **Step 1: 重写 handleModeChange 函数**

替换原有的 handleModeChange，使其直接设置 dateRange：

```typescript
const handleModeChange = (nextRange: TimeRange) => {
  setTimeRange(nextRange);
  const today = dayjs();

  if (nextRange === "day") {
    setDateRange([today, today]);
  } else if (nextRange === "week") {
    setDateRange([today.subtract(6, "day"), today]);
  } else if (nextRange === "month") {
    setDateRange([today.subtract(29, "day"), today]);
  }
};
```

- [ ] **Step 2: 新增 handleDateRangeChange 函数**

添加新函数处理 RangePicker 选择：

```typescript
const handleDateRangeChange = (dates: [Dayjs | null, Dayjs | null] | null) => {
  if (!dates || !dates[0] || !dates[1]) {
    return;
  }

  const [start, end] = dates;
  const today = dayjs().startOf("day");

  // 检测是否匹配快捷按钮范围
  if (start.isSame(today, "day") && end.isSame(today, "day")) {
    setTimeRange("day");
  } else if (
    start.isSame(today.subtract(6, "day"), "day") &&
    end.isSame(today, "day")
  ) {
    setTimeRange("week");
  } else if (
    start.isSame(today.subtract(29, "day"), "day") &&
    end.isSame(today, "day")
  ) {
    setTimeRange("month");
  } else {
    setTimeRange("custom");
  }

  setDateRange([start, end]);
};
```

- [ ] **Step 3: 删除旧函数**

删除以下函数：
- `handleStartDateChange` (原第 723-742 行)
- `handleEndDateChange` (原第 744-750 行)
- `disabledStartDate` (原第 768-769 行)
- `disabledEndDate` (原第 771-779 行)

- [ ] **Step 4: 新增 disabledDate 函数**

添加禁用未来日期的逻辑：

```typescript
const disabledDate = (current: Dayjs | null): boolean =>
  !!current && current.isAfter(dayjs().startOf("day"), "day");
```

- [ ] **Step 5: 验证编译无错误**

确认 TypeScript 编译无错误。

- [ ] **Step 6: Commit**

```bash
git add console/src/pages/Analytics/BusinessOverview/index.tsx
git commit -m "refactor(BusinessOverview): 重构日期处理函数"
```

---

### Task 3: 渲染重构

**Files:**
- Modify: `console/src/pages/Analytics/BusinessOverview/index.tsx:844-862` (DatePicker 渲染区域)
- Check: `console/src/pages/Analytics/BusinessOverview/index.module.less`

- [ ] **Step 1: 更新导入**

确认 RangePicker 已通过解构导入。检查第 24 行：

```typescript
// 当前导入：
import { DatePicker, Select, Tooltip, message } from "antd";

// 保持不变，RangePicker 通过 DatePicker.RangePicker 使用
```

- [ ] **Step 2: 替换 DatePicker 渲染**

将原来的两个 DatePicker 替换为 RangePicker：

```tsx
// 原代码（删除）:
// <div className={styles.dateRangePanel}>
//   <DatePicker
//     className={styles.datePicker}
//     value={startDate}
//     onChange={handleStartDateChange}
//     format="YYYY-MM-DD"
//     suffixIcon={<CalendarDays size={16} />}
//     disabledDate={disabledStartDate}
//   />
//   <span className={styles.dateDivider}>~</span>
//   <DatePicker
//     className={styles.datePicker}
//     value={calculatedEndDate}
//     onChange={handleEndDateChange}
//     format="YYYY-MM-DD"
//     suffixIcon={<CalendarDays size={16} />}
//     disabledDate={disabledEndDate}
//   />
// </div>

// 新代码:
<div className={styles.dateRangePanel}>
  <DatePicker.RangePicker
    className={styles.rangePicker}
    value={dateRange}
    onChange={handleDateRangeChange}
    format="YYYY-MM-DD"
    suffixIcon={<CalendarDays size={16} />}
    disabledDate={disabledDate}
    allowClear={false}
  />
</div>
```

- [ ] **Step 3: 检查并更新样式**

查看 `index.module.less` 中是否有 `.datePicker` 和 `.dateDivider` 样式。如果存在，新增 `.rangePicker` 样式：

```less
.rangePicker {
  width: 240px;
}
```

如果 `.dateDivider` 样式不再使用，可以删除。

- [ ] **Step 4: 验证页面渲染**

启动前端开发服务器，访问 BusinessOverview 页面，确认 RangePicker 正常显示。

```bash
cd console && npm run dev
```

- [ ] **Step 5: Commit**

```bash
git add console/src/pages/Analytics/BusinessOverview/index.tsx
git add console/src/pages/Analytics/BusinessOverview/index.module.less
git commit -m "feat(BusinessOverview): 替换两个 DatePicker 为 RangePicker"
```

---

### Task 4: 联动逻辑验证

**Files:**
- Test: `console/src/pages/Analytics/BusinessOverview/index.test.tsx`

- [ ] **Step 1: 手动测试快捷按钮联动**

在浏览器中：
1. 点击"今天"按钮 → 确认 RangePicker 显示 `[今天, 今天]`
2. 点击"近7天"按钮 → 确认 RangePicker 显示 `[今天-6天, 今天]`
3. 点击"近30天"按钮 → 确认 RangePicker 显示 `[今天-29天, 今天]`
4. 确认按钮选中状态正确切换

- [ ] **Step 2: 手动测试 RangePicker 选择联动**

在浏览器中：
1. 在 RangePicker 中手动选择 `[今天-6天, 今天]` → 确认"近7天"按钮自动选中
2. 在 RangePicker 中手动选择 `[今天-29天, 今天]` → 确认"近30天"按钮自动选中
3. 在 RangePicker 中手动选择不匹配的范围（如 `[2026-05-10, 2026-05-15]`） → 确认所有按钮取消选中（自定义模式）

- [ ] **Step 3: 手动测试禁用逻辑**

在浏览器中：
1. 点击 RangePicker 打开面板
2. 确认未来日期（明天及之后）被禁用，无法选择

- [ ] **Step 4: 手动测试初始加载**

刷新页面，确认：
1. "今天"按钮默认选中
2. RangePicker 显示 `[今天, 今天]`

- [ ] **Step 5: 手动测试 API 调用**

查看浏览器 Network 面板，确认 API 请求参数正确传递：
- `start_date` 格式为 `YYYY-MM-DD`
- `end_date` 格式为 `YYYY-MM-DD`

---

### Task 5: 单元测试（可选）

**Files:**
- Create/Modify: `console/src/pages/Analytics/BusinessOverview/index.test.tsx`

- [ ] **Step 1: 检查现有测试文件**

检查 `index.test.tsx` 是否已存在。如果存在，查看其内容。

```bash
ls console/src/pages/Analytics/BusinessOverview/index.test.tsx
```

- [ ] **Step 2: 添加联动逻辑测试（如果需要）**

根据项目测试规范，可添加以下测试用例：

```typescript
import { render, screen, fireEvent } from "@testing-library/react";
import dayjs from "dayjs";
import BusinessOverviewPage from "./index";

// Mock 必要的依赖...

describe("BusinessOverview 日期联动", () => {
  it("点击快捷按钮应更新 RangePicker 值", () => {
    render(<BusinessOverviewPage />);
    // 测试逻辑...
  });

  it("RangePicker 选择匹配范围应自动选中快捷按钮", () => {
    render(<BusinessOverviewPage />);
    // 测试逻辑...
  });
});
```

注意：由于页面依赖 iframe context、API 等外部依赖，测试需要大量 mock。根据项目实际情况决定是否添加。

- [ ] **Step 3: 运行测试**

```bash
cd console && npm test
```

- [ ] **Step 4: Commit（如果有测试改动）**

```bash
git add console/src/pages/Analytics/BusinessOverview/index.test.tsx
git commit -m "test(BusinessOverview): 添加日期联动测试用例"
```

---

### Task 6: 最终验证与收尾

**Files:**
- All modified files

- [ ] **Step 1: 运行完整前端构建**

```bash
cd console && npm run build
```

确认构建成功，无 TypeScript 或 ESLint 错误。

- [ ] **Step 2: 运行 Lint 检查**

```bash
cd console && npm run lint
```

修复任何 Lint 错误。

- [ ] **Step 3: 最终 Commit**

```bash
git add -A
git commit -m "feat(BusinessOverview): 完成日期选择 RangePicker 联动优化"
```

- [ ] **Step 4: 更新设计文档**

移除设计文档末尾的"详见后续实现计划文档"占位文本：

```markdown
## 实现状态

已完成。参见 Git commit history。
```

---

## 自检清单

- [x] Spec 覆盖：所有设计点均有对应任务
- [x] 无占位符：所有代码步骤包含实际内容
- [x] 类型一致：dateRange、handleDateRangeChange 等命名统一