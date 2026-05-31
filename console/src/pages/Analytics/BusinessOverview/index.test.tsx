import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import BusinessOverviewPage, { buildTrendSvgData } from "./index";

vi.mock("echarts-for-react", () => ({
  default: (props: { style?: Record<string, unknown> }) => (
    <div data-testid="echarts" style={props.style} />
  ),
}));

const tracingApiMock = vi.hoisted(() => ({
  getOverview: vi.fn(),
  getGrowthStats: vi.fn(),
  getHourlyTrend: vi.fn(),
  getDailyTrend: vi.fn(),
  getUsers: vi.fn(),
  getSkills: vi.fn(),
  getMCPSummary: vi.fn(),
  getTaskStatusSummary: vi.fn(),
  getDepthSummary: vi.fn(),
  getErrorSummary: vi.fn(),
  getSources: vi.fn(),
}));
const htmlPreviewEventsApiMock = vi.hoisted(() => ({
  getSummary: vi.fn(),
}));

vi.mock("../../../api/modules/tracing", () => ({
  tracingApi: tracingApiMock,
}));

vi.mock("../../../api/modules/htmlPreviewEvents", () => ({
  htmlPreviewEventsApi: htmlPreviewEventsApiMock,
}));

vi.mock("../../../stores/iframeStore", () => ({
  useIframeStore: (selector: (state: unknown) => unknown) =>
    selector({
      isSuperManager: true,
      source: "CMSJY",
      bbk: undefined,
    }),
}));

vi.mock("./components/UserDetailModal", () => ({
  default: () => null,
}));

vi.mock("./components/SkillDetailModal", () => ({
  default: () => null,
}));

describe("BusinessOverview trend chart", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    tracingApiMock.getOverview.mockResolvedValue({
      total_users: 120,
      total_sessions: 80,
      total_tokens: 56000,
      total_skill_calls: 40,
      total_conversations: 160,
      branch_breakdown: {
        users: [],
        sessions: [],
        tokens: [],
        skills: [],
        cron_tasks: [],
      },
    });
    tracingApiMock.getGrowthStats.mockResolvedValue({
      callsGrowth: 10,
      tokensGrowth: 12,
      sessionGrowth: 8,
      userGrowth: 5,
      skillGrowth: 3,
      cronGrowth: 2,
      avgRoundsGrowth: 4,
      multiRoundRatioGrowth: 1,
      avgDurationGrowth: 6,
      avgSessionsPerUserGrowth: 7,
    });
    tracingApiMock.getHourlyTrend.mockResolvedValue({
      trendData: [
        { date: "2026-05-19 09:00:00", users: 3200, calls: 15800, tokens: 0 },
        { date: "2026-05-19 10:00:00", users: 2100, calls: 9200, tokens: 0 },
      ],
    });
    tracingApiMock.getDailyTrend.mockResolvedValue({ trendData: [] });
    tracingApiMock.getUsers.mockResolvedValue({ items: [], total: 0 });
    tracingApiMock.getSkills.mockResolvedValue({ items: [], total: 0 });
    tracingApiMock.getMCPSummary.mockResolvedValue({
      total_calls: 0,
      error_count: 0,
      server_count: 0,
    });
    tracingApiMock.getTaskStatusSummary.mockResolvedValue({
      total_tasks: 0,
      success: 0,
      failed: 0,
      cancelled: 0,
    });
    tracingApiMock.getDepthSummary.mockResolvedValue({
      avg_rounds: 2,
      multi_round_ratio: 10,
      avg_duration_seconds: 30,
      avg_sessions_per_user: 1.5,
    });
    tracingApiMock.getErrorSummary.mockResolvedValue({
      total_errors: 0,
      model_errors: 0,
      tool_errors: 0,
      other_errors: 0,
    });
    tracingApiMock.getSources.mockResolvedValue({ sources: ["CMSJY"] });
    htmlPreviewEventsApiMock.getSummary.mockResolvedValue({
      items: [
        {
          button_label: "立即跟进",
          button_id: "follow",
          button_name: "立即跟进",
          file_name: "到期客户名单[auto-preview].html",
          click_count: 12,
          last_clicked_at: "2026-05-19T10:30:00",
        },
      ],
    });
  });

  function renderBusinessOverview() {
    return render(
      <MemoryRouter>
        <BusinessOverviewPage />
      </MemoryRouter>,
    );
  }

  it("builds dynamic y-axis ticks from actual trend maxima", () => {
    const trendSvg = buildTrendSvgData([
      { date: "2026-05-19", users: 3200, calls: 15800 },
      { date: "2026-05-20", users: 2100, calls: 9200 },
    ]);

    expect(trendSvg.leftAxisTicks.map((tick) => tick.label)).toEqual([
      "5K",
      "4K",
      "3K",
      "2K",
      "1K",
      "0",
    ]);
    expect(trendSvg.rightAxisTicks.map((tick) => tick.label)).toEqual([
      "2W",
      "1.6W",
      "1.2W",
      "0.8W",
      "0.4W",
      "0",
    ]);
  });

  it("shows the real values when hovering a trend column", async () => {
    renderBusinessOverview();

    await waitFor(() => {
      expect(screen.getByTestId("trend-hover-zone-0")).toBeInTheDocument();
    });

    fireEvent.mouseEnter(screen.getByTestId("trend-hover-zone-0"));

    const tooltip = await screen.findByTestId("trend-tooltip");
    expect(within(tooltip).getByText("09:00")).toBeInTheDocument();
    expect(within(tooltip).getByText("3,200")).toBeInTheDocument();
    expect(within(tooltip).getByText("15,800")).toBeInTheDocument();
  });

  it("maps avgDurationGrowth into the average duration growth card", async () => {
    renderBusinessOverview();

    expect(await screen.findByText("30s")).toBeInTheDocument();
    expect(
      await screen.findByText((_, element) =>
        typeof element?.className === "string" &&
        element.className.includes("metricChangeUp") &&
        (element.textContent || "").includes("环比+6.0%"),
      ),
    ).toBeInTheDocument();
  });

  it("renders HTML preview click statistics inside business overview", async () => {
    renderBusinessOverview();

    expect(await screen.findByText("HTML 预览点击统计")).toBeInTheDocument();
    expect(await screen.findByText("点击总数")).toBeInTheDocument();
    expect(await screen.findByText("立即跟进")).toBeInTheDocument();
    expect(htmlPreviewEventsApiMock.getSummary).toHaveBeenCalled();
  });
});
