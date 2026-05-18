# Business Overview UI Restoration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the desktop `BusinessOverview` page so it visually matches the approved reference layout while preserving existing data fetching, filtering, ranking pagination, and modal interactions.

**Architecture:** Keep all existing tracing API calls and interaction handlers in `BusinessOverview`, but reorganize the page into screenshot-aligned presentation sections driven by small display-model helpers. Use page-local helper types and mapping functions to convert existing stats into KPI cards, trend data, ranking cards, depth stats, and donut summaries without changing backend contracts.

**Tech Stack:** React 18, TypeScript, Ant Design 5, Less modules, Vitest, Testing Library

---

## File Structure

### Files to Modify

- `console/src/pages/Analytics/BusinessOverview/index.tsx`
  Responsibility: keep data fetching and interaction state, add screenshot-aligned section layout, add display-model mapping, and preserve modal entry points.
- `console/src/pages/Analytics/BusinessOverview/index.module.less`
  Responsibility: replace old dashboard styling with desktop-first screenshot-aligned grid, card, ranking, trend, and donut styles.
- `console/src/pages/Analytics/BusinessOverview/types.ts`
  Responsibility: add page-local display types and formatting helpers used by the new presentation mapping.

### Files to Create

- `console/src/pages/Analytics/BusinessOverview/index.test.tsx`
  Responsibility: verify the restored page still renders key sections, filtering UI, and preserved modal/ranking interaction hooks under mocked data.

## Task 1: Lock Display Models And Formatting Helpers

**Files:**
- Modify: `console/src/pages/Analytics/BusinessOverview/types.ts`
- Test: `console/src/pages/Analytics/BusinessOverview/index.test.tsx`

- [ ] **Step 1: Write the failing helper-driven render test**

```tsx
import { render, screen } from "@testing-library/react";
import { vi } from "vitest";
import BusinessOverviewPage from "./index";

vi.mock("../../../api/modules/tracing", () => ({
  tracingApi: {
    getSources: vi.fn().mockResolvedValue({ sources: ["RMASSIST"] }),
    getOverview: vi.fn().mockResolvedValue({
      total_users: 3245,
      total_tokens: 987654,
      input_tokens: 456789,
      output_tokens: 530865,
      total_conversations: 8762,
      total_calls: 1296,
      avg_duration: 1.21,
      model_distribution: [],
    }),
    getGrowthStats: vi.fn().mockResolvedValue({
      callsGrowth: 15.6,
      tokensGrowth: 9.3,
      sessionGrowth: 11.4,
      userGrowth: 12.5,
      platformGrowth: 18.7,
      avgDurationGrowth: -0.15,
    }),
    getChannelDistribution: vi.fn().mockResolvedValue({
      platformUserDistribution: [
        { name: "上海分行", value: 24.1 },
        { name: "杭州分行", value: 19.7 },
      ],
      platformCallDistribution: [
        { name: "杭州分行", value: 27.3 },
        { name: "上海分行", value: 20.1 },
      ],
      totalPlatforms: 2,
    }),
    getDailyTrend: vi.fn().mockResolvedValue({
      trendData: [
        { date: "2026-05-10", calls: 10, tokens: 100, users: 3 },
        { date: "2026-05-11", calls: 12, tokens: 120, users: 4 },
      ],
    }),
    getUsers: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    getSkills: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    getMCPServers: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  },
}));

vi.mock("../../../stores/iframeStore", () => ({
  useIframeStore: (selector: (state: any) => any) =>
    selector({ isSuperManager: true, source: "RMASSIST" }),
}));

test("renders restored KPI and analysis section titles from mapped data", async () => {
  render(<BusinessOverviewPage />);

  expect(await screen.findByText("总览")).toBeInTheDocument();
  expect(await screen.findByText("活跃用户数")).toBeInTheDocument();
  expect(await screen.findByText("调用量趋势")).toBeInTheDocument();
  expect(await screen.findByText("活跃用户排行榜")).toBeInTheDocument();
  expect(await screen.findByText("使用深度")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- src/pages/Analytics/BusinessOverview/index.test.tsx`

Expected: FAIL because `index.test.tsx` does not exist yet and the restored section titles are not rendered by the current page.

- [ ] **Step 3: Add display types and formatting helpers**

```ts
export interface BreakdownItem {
  name: string;
  value: number;
  percentText: string;
}

export interface OverviewMetricCard {
  key: string;
  title: string;
  valueText: string;
  changeText: string;
  changeDirection: "up" | "down" | "flat";
  accentColor: string;
  breakdown: BreakdownItem[];
}

export interface DepthStatCard {
  key: string;
  title: string;
  valueText: string;
  changeText: string;
}

export function formatPercent(value: number | undefined | null): string {
  const numValue = typeof value === "number" && !Number.isNaN(value) ? value : 0;
  return `${numValue.toFixed(1)}%`;
}

export function toChangeDirection(
  value: number | undefined | null,
): "up" | "down" | "flat" {
  const numValue = typeof value === "number" && !Number.isNaN(value) ? value : 0;
  if (numValue > 0) return "up";
  if (numValue < 0) return "down";
  return "flat";
}
```

- [ ] **Step 4: Run test to verify helper additions compile**

Run: `npm test -- src/pages/Analytics/BusinessOverview/index.test.tsx`

Expected: FAIL moves forward from missing helper types to missing restored layout content in `index.tsx`.

- [ ] **Step 5: Commit**

```bash
git add console/src/pages/Analytics/BusinessOverview/types.ts console/src/pages/Analytics/BusinessOverview/index.test.tsx
git commit -m "test(analytics): add business overview restoration scaffolding"
```

## Task 2: Rebuild The Page Skeleton Around Screenshot Sections

**Files:**
- Modify: `console/src/pages/Analytics/BusinessOverview/index.tsx`
- Test: `console/src/pages/Analytics/BusinessOverview/index.test.tsx`

- [ ] **Step 1: Extend the failing test with screenshot section expectations**

```tsx
test("renders screenshot-aligned desktop sections", async () => {
  render(<BusinessOverviewPage />);

  expect(await screen.findByText("今天")).toBeInTheDocument();
  expect(screen.getByText("近7天")).toBeInTheDocument();
  expect(screen.getByText("近30天")).toBeInTheDocument();
  expect(await screen.findByText("任务执行概览")).toBeInTheDocument();
  expect(await screen.findByText("技能使用TOP5")).toBeInTheDocument();
  expect(await screen.findByText("MCP调用概览")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- src/pages/Analytics/BusinessOverview/index.test.tsx`

Expected: FAIL because the old JSX structure does not render the approved screenshot-aligned section layout.

- [ ] **Step 3: Add page-local display mapping and new section JSX**

```tsx
const metricCards = buildMetricCards({
  overviewStats,
  growthStats,
  channelDistribution,
});

const depthCards = buildDepthCards({
  overviewStats,
  growthStats,
  callsUsers,
  activeUsers,
});

return (
  <div className={styles.businessOverviewPage}>
    <header className={styles.pageHeader}>
      <div className={styles.pageTitleBlock}>
        <h1 className={styles.pageTitle}>总览</h1>
      </div>
      <div className={styles.toolbar}>
        <div className={styles.segmentedControl}>{/* existing time controls */}</div>
        <div className={styles.filters}>{/* existing date and select controls */}</div>
      </div>
    </header>

    <section className={styles.metricGrid}>
      {metricCards.map((card) => (
        <article key={card.key} className={styles.metricPanel}>
          <div className={styles.metricPanelHeader}>{card.title}</div>
          <div className={styles.metricPanelValue}>{card.valueText}</div>
          <div className={styles.metricPanelChange}>{card.changeText}</div>
          <div className={styles.metricBreakdownList}>{renderBreakdown(card.breakdown)}</div>
        </article>
      ))}
    </section>

    <section className={styles.analysisGrid}>
      <article className={styles.trendPanel}>{renderLineChart(trendData)}</article>
      <article className={styles.rankingPanel}>{renderUserList(activeUsers, "calls")}</article>
      <article className={styles.depthPanel}>
        {depthCards.map((card) => (
          <div key={card.key} className={styles.depthStatCard}>
            <span>{card.title}</span>
            <strong>{card.valueText}</strong>
          </div>
        ))}
      </article>
    </section>

    <section className={styles.summaryGrid}>
      <article className={styles.donutPanel}>{renderExecutionSummary()}</article>
      <article className={styles.topListPanel}>{renderSkillList(skills)}</article>
      <article className={styles.donutPanel}>{renderMcpSummary()}</article>
    </section>
  </div>
);
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- src/pages/Analytics/BusinessOverview/index.test.tsx`

Expected: PASS with the restored section titles and toolbar controls rendered.

- [ ] **Step 5: Commit**

```bash
git add console/src/pages/Analytics/BusinessOverview/index.tsx console/src/pages/Analytics/BusinessOverview/index.test.tsx
git commit -m "feat(analytics): rebuild business overview layout"
```

## Task 3: Apply Screenshot-Matched Desktop Styling

**Files:**
- Modify: `console/src/pages/Analytics/BusinessOverview/index.module.less`
- Test: `console/src/pages/Analytics/BusinessOverview/index.test.tsx`

- [ ] **Step 1: Extend the test to assert the new desktop card structure exists**

```tsx
test("renders six top metric panels and desktop summary sections", async () => {
  const { container } = render(<BusinessOverviewPage />);

  await screen.findByText("活跃用户数");

  expect(container.querySelectorAll("[data-testid='overview-metric-card']")).toHaveLength(6);
  expect(container.querySelector("[data-testid='overview-analysis-grid']")).toBeTruthy();
  expect(container.querySelector("[data-testid='overview-summary-grid']")).toBeTruthy();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- src/pages/Analytics/BusinessOverview/index.test.tsx`

Expected: FAIL because the test ids and desktop-only structural wrappers have not been added yet.

- [ ] **Step 3: Add desktop structure hooks in JSX and replace old Less with screenshot-aligned styles**

```tsx
<section className={styles.metricGrid} data-testid="overview-metric-grid">
  {metricCards.map((card) => (
    <article
      key={card.key}
      className={styles.metricPanel}
      data-testid="overview-metric-card"
    >
      ...
    </article>
  ))}
</section>

<section className={styles.analysisGrid} data-testid="overview-analysis-grid">
  ...
</section>

<section className={styles.summaryGrid} data-testid="overview-summary-grid">
  ...
</section>
```

```less
.businessOverviewPage {
  min-width: 1360px;
  padding: 24px 28px 32px;
  background: #f5f7fb;
}

.metricGrid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}

.metricPanel,
.trendPanel,
.rankingPanel,
.depthPanel,
.donutPanel,
.topListPanel {
  background: #ffffff;
  border: 1px solid #e8edf5;
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
}

.analysisGrid,
.summaryGrid {
  display: grid;
  grid-template-columns: 2.1fr 1.8fr 1.8fr;
  gap: 16px;
  margin-bottom: 16px;
}

.depthPanel {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  padding: 16px;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- src/pages/Analytics/BusinessOverview/index.test.tsx`

Expected: PASS with six metric cards and the restored desktop grids present.

- [ ] **Step 5: Commit**

```bash
git add console/src/pages/Analytics/BusinessOverview/index.tsx console/src/pages/Analytics/BusinessOverview/index.module.less console/src/pages/Analytics/BusinessOverview/index.test.tsx
git commit -m "feat(analytics): style business overview to match screenshot"
```

## Task 4: Preserve Existing Interactions Under The New Layout

**Files:**
- Modify: `console/src/pages/Analytics/BusinessOverview/index.tsx`
- Modify: `console/src/pages/Analytics/BusinessOverview/index.test.tsx`

- [ ] **Step 1: Write the failing interaction preservation tests**

```tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

test("opens skill detail modal from restored skill ranking card", async () => {
  render(<BusinessOverviewPage />);

  const skillRow = await screen.findByText("票务分析");
  fireEvent.click(skillRow);

  await waitFor(() => {
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });
});

test("keeps platform filter enabled for super managers", async () => {
  render(<BusinessOverviewPage />);

  expect(await screen.findByText("全部平台")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- src/pages/Analytics/BusinessOverview/index.test.tsx`

Expected: FAIL if the restored layout broke click targets, modal wiring, or filter rendering.

- [ ] **Step 3: Keep click handlers, scroll containers, and modal props wired through the new markup**

```tsx
<div className={styles.skillListScroll} onScroll={handleSkillsScroll}>
  {renderSkillList(skills)}
</div>

<div
  className={styles.skillRowItem}
  onClick={() => {
    setSelectedSkillName(skill.skill_name);
    setSkillModalOpen(true);
  }}
>
  ...
</div>

<SkillDetailModal
  open={skillModalOpen}
  skillName={selectedSkillName}
  startDate={startDate.format("YYYY-MM-DD")}
  endDate={calculatedEndDate.format("YYYY-MM-DD")}
  sourceId={platform}
  onClose={() => {
    setSkillModalOpen(false);
    setSelectedSkillName("");
  }}
/>;
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- src/pages/Analytics/BusinessOverview/index.test.tsx`

Expected: PASS with modal entry points and filter controls preserved under the restored layout.

- [ ] **Step 5: Commit**

```bash
git add console/src/pages/Analytics/BusinessOverview/index.tsx console/src/pages/Analytics/BusinessOverview/index.test.tsx
git commit -m "test(analytics): preserve business overview interactions"
```

## Task 5: Verify The Full Page And Clean Up

**Files:**
- Modify: `console/src/pages/Analytics/BusinessOverview/index.tsx`
- Modify: `console/src/pages/Analytics/BusinessOverview/index.module.less`
- Modify: `console/src/pages/Analytics/BusinessOverview/types.ts`
- Test: `console/src/pages/Analytics/BusinessOverview/index.test.tsx`

- [ ] **Step 1: Run the focused test file**

Run: `npm test -- src/pages/Analytics/BusinessOverview/index.test.tsx`

Expected: PASS with all restored layout and interaction checks green.

- [ ] **Step 2: Run the full console test suite**

Run: `npm run test:run`

Expected: PASS for existing console tests, confirming the page refactor did not regress unrelated UI behavior.

- [ ] **Step 3: Run type/build verification**

Run: `npm run build`

Expected: PASS with no TypeScript or Vite build errors from the restored page.

- [ ] **Step 4: Run formatting or lint verification if needed**

Run: `npm run format:check`

Expected: PASS, or if it fails on touched files only, apply formatting and rerun until PASS.

- [ ] **Step 5: Commit**

```bash
git add console/src/pages/Analytics/BusinessOverview/index.tsx console/src/pages/Analytics/BusinessOverview/index.module.less console/src/pages/Analytics/BusinessOverview/types.ts console/src/pages/Analytics/BusinessOverview/index.test.tsx
git commit -m "feat(analytics): complete business overview ui restoration"
```

## Self-Review

### Spec Coverage

- 顶部筛选栏重构：Task 2, Task 3
- 六张 KPI 卡：Task 1, Task 2, Task 3
- 趋势图、活跃用户榜、使用深度：Task 2, Task 3
- 任务执行概览、技能 TOP5、MCP 概览：Task 2, Task 3
- 保留筛选、弹窗、滚动加载：Task 4
- 桌面端优先和样式统一：Task 3
- 验收与构建验证：Task 5

### Placeholder Scan

- No `TODO`, `TBD`, or deferred “implement later” language remains.
- Each task contains exact file paths, commands, and concrete code targets.

### Type Consistency

- The plan consistently uses `OverviewMetricCard`, `DepthStatCard`, and `BreakdownItem` as the display-model layer.
- Layout tasks reference the same `metricCards`, `depthCards`, and preserved modal state names used in the existing page.
