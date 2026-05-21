import { render, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import UserDetailModal from "./index";

const tracingApiMock = vi.hoisted(() => ({
  getUserStats: vi.fn(),
  getSessions: vi.fn(),
  getSessionStats: vi.fn(),
  getTraces: vi.fn(),
}));

vi.mock("../../../../../api/modules/tracing", () => ({
  tracingApi: tracingApiMock,
}));

vi.mock("./UserStatsHeader", () => ({
  default: () => <div data-testid="user-stats-header" />,
}));

vi.mock("./SessionCardList", () => ({
  default: () => <div data-testid="session-card-list" />,
}));

vi.mock("./ReadOnlySessionChat", () => ({
  default: () => <div data-testid="readonly-session-chat" />,
}));

describe("UserDetailModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    tracingApiMock.getUserStats.mockResolvedValue({});
    tracingApiMock.getSessions.mockResolvedValue({
      items: [
        {
          session_id: "session-older",
          session_name: "历史会话",
          total_traces: 1,
          total_tokens: 12,
          total_skills: 0,
          channel: "web",
          last_active: "2026-05-01T10:00:00Z",
        },
      ],
      total: 1,
    });
    tracingApiMock.getSessionStats.mockResolvedValue({});
    tracingApiMock.getTraces.mockResolvedValue({ items: [], total: 0 });
  });

  it("loads all sessions and traces for the selected user regardless of dashboard date", async () => {
    render(
      <UserDetailModal
        open
        userId="user-001"
        startDate="2026-05-20"
        endDate="2026-05-20"
        sourceId="CMSJY"
        bbkIds="100"
        onClose={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(tracingApiMock.getSessions).toHaveBeenCalled();
    });

    expect(tracingApiMock.getUserStats).toHaveBeenCalledWith(
      "user-001",
      "2026-05-20",
      "2026-05-20",
      "CMSJY",
      "100",
    );
    expect(tracingApiMock.getSessions).toHaveBeenCalledWith(1, 10, {
      user_id: "user-001",
      source_id: "CMSJY",
      bbk_ids: "100",
    });

    await waitFor(() => {
      expect(tracingApiMock.getTraces).toHaveBeenCalled();
    });

    expect(tracingApiMock.getSessionStats).toHaveBeenCalledWith(
      "session-older",
      undefined,
      undefined,
      "CMSJY",
      "100",
    );
    expect(tracingApiMock.getTraces).toHaveBeenCalledWith(1, 10, {
      session_id: "session-older",
      source_id: "CMSJY",
      bbk_ids: "100",
    });
  });
});
