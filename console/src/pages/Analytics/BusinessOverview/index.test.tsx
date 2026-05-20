import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import BusinessOverviewPage, { buildTrendSvgData } from "./index";

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
  getSources: vi.fn(),
}));

vi.mock("../../../api/modules/tracing", () => ({
  tracingApi: tracingApiMock,
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
      avgStayGrowth: 6,
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
      avg_stay_seconds: 30,
      avg_sessions_per_user: 1.5,
    });
    tracingApiMock.getSources.mockResolvedValue({ sources: ["CMSJY"] });
  });

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
    render(<BusinessOverviewPage />);

    await waitFor(() => {
      expect(screen.getByTestId("trend-hover-zone-0")).toBeInTheDocument();
    });

    fireEvent.mouseEnter(screen.getByTestId("trend-hover-zone-0"));

    const tooltip = await screen.findByTestId("trend-tooltip");
    expect(within(tooltip).getByText("09:00")).toBeInTheDocument();
    expect(within(tooltip).getByText("3,200")).toBeInTheDocument();
    expect(within(tooltip).getByText("15,800")).toBeInTheDocument();
  });

  it("maps avgStayGrowth into the average duration growth card", async () => {
    render(<BusinessOverviewPage />);

    expect(await screen.findByText("30s")).toBeInTheDocument();
    expect(
      await screen.findByText((_, element) =>
        typeof element?.className === "string" &&
        element.className.includes("metricChangeUp") &&
        (element.textContent || "").includes("环比+6.0%"),
      ),
    ).toBeInTheDocument();
  });
});
