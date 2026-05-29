import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ExpandablePanel from ".";

const mocks = vi.hoisted(() => ({
  navigate: vi.fn(),
  setSessionLoading: vi.fn(),
}));

vi.mock("react-router-dom", () => ({
  useNavigate: () => mocks.navigate,
}));

vi.mock("@/components/agentscope-chat", () => ({
  useChatAnywhereSessionsState: () => ({
    currentSessionId: "chat-1",
    setSessionLoading: mocks.setSessionLoading,
  }),
}));

describe("ExpandablePanel history", () => {
  beforeEach(() => {
    mocks.navigate.mockReset();
    mocks.setSessionLoading.mockReset();
  });

  it("ignores clicks on the already active session", () => {
    const onClose = vi.fn();

    render(
      <ExpandablePanel
        visible
        type="history"
        onClose={onClose}
        tasks={[]}
        sessions={[
          {
            id: "chat-1",
            name: "current chat",
            messages: [],
          },
        ]}
        onTaskClick={vi.fn()}
        toolbarRef={{ current: document.createElement("div") }}
      />,
    );

    fireEvent.click(screen.getByText("current chat"));

    expect(mocks.setSessionLoading).not.toHaveBeenCalled();
    expect(mocks.navigate).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
  });

  it("ignores clicks when the active session is addressed by realId", () => {
    const onClose = vi.fn();

    render(
      <ExpandablePanel
        visible
        type="history"
        onClose={onClose}
        tasks={[]}
        sessions={[
          {
            id: "temp-1",
            realId: "chat-1",
            name: "current chat by real id",
            messages: [],
          } as any,
        ]}
        onTaskClick={vi.fn()}
        toolbarRef={{ current: document.createElement("div") }}
      />,
    );

    fireEvent.click(screen.getByText("current chat by real id"));

    expect(mocks.setSessionLoading).not.toHaveBeenCalled();
    expect(mocks.navigate).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
  });

  it("loads and navigates when clicking a different session", () => {
    const onClose = vi.fn();

    render(
      <ExpandablePanel
        visible
        type="history"
        onClose={onClose}
        tasks={[]}
        sessions={[
          {
            id: "chat-2",
            name: "other chat",
            messages: [],
          },
        ]}
        onTaskClick={vi.fn()}
        toolbarRef={{ current: document.createElement("div") }}
      />,
    );

    fireEvent.click(screen.getByText("other chat"));

    expect(mocks.setSessionLoading).toHaveBeenCalledWith(true);
    expect(mocks.navigate).toHaveBeenCalledWith("/chat/chat-2", {
      replace: true,
    });
    expect(onClose).toHaveBeenCalled();
  });
});

describe("ExpandablePanel tasks", () => {
  beforeEach(() => {
    mocks.navigate.mockReset();
    mocks.setSessionLoading.mockReset();
  });

  it("shows completed status instead of scheduled result preview", () => {
    render(
      <ExpandablePanel
        visible
        type="tasks"
        onClose={vi.fn()}
        tasks={[
          {
            id: "job-1",
            name: "daily task",
            enabled: true,
            schedule: {
              type: "cron",
              cron: "0 9 * * *",
              timezone: "Asia/Shanghai",
            },
            task_type: "agent",
            request: {
              input: [{ role: "user", content: "ping" }],
            },
            dispatch: {
              type: "channel",
              channel: "console",
              target: {
                user_id: "user-1",
                session_id: "session-1",
              },
            },
            task: {
              visible_in_my_tasks: true,
              has_scheduled_result: true,
              latest_scheduled_preview: "scheduled result preview",
              unread_execution_count: 0,
              is_running: false,
              is_paused: false,
              pause_reason: null,
              last_scheduled_run_at: "2026-05-21T08:00:00Z" as any,
            },
          } as any,
        ]}
        sessions={[]}
        onTaskClick={vi.fn()}
        toolbarRef={{ current: document.createElement("div") }}
      />,
    );

    expect(screen.getByText("已完成")).toBeInTheDocument();
    expect(screen.queryByText("scheduled result preview")).toBeNull();
  });

  it("shows unread badge without hiding task actions", () => {
    const { container } = render(
      <ExpandablePanel
        visible
        type="tasks"
        onClose={vi.fn()}
        tasks={[
          {
            id: "job-1",
            name: "daily task",
            enabled: true,
            schedule: {
              type: "cron",
              cron: "0 9 * * *",
              timezone: "Asia/Shanghai",
            },
            task_type: "agent",
            request: {
              input: [{ role: "user", content: "ping" }],
            },
            dispatch: {
              type: "channel",
              channel: "console",
              target: {
                user_id: "user-1",
                session_id: "session-1",
              },
            },
            task: {
              visible_in_my_tasks: true,
              has_scheduled_result: true,
              latest_scheduled_preview: "",
              unread_execution_count: 3,
              is_running: false,
              is_paused: false,
              pause_reason: null,
            },
          } as any,
        ]}
        sessions={[]}
        onTaskClick={vi.fn()}
        toolbarRef={{ current: document.createElement("div") }}
      />,
    );

    expect(screen.getByText("3")).toBeInTheDocument();
    expect(
      container.querySelector(".expandable-panel-task-action-trigger"),
    ).toBeInTheDocument();
  });
});
