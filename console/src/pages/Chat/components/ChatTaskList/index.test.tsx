import React from "react";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { CronJobSpecOutput } from "@/api/types";
import ChatTaskList from ".";

function taskJob(
  overrides: Partial<CronJobSpecOutput> = {},
): CronJobSpecOutput {
  return {
    id: "job-1",
    name: "每日巡检",
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
      has_scheduled_result: false,
      latest_scheduled_preview: "",
      unread_execution_count: 0,
      is_running: false,
      is_paused: false,
      pause_reason: null,
    },
    ...overrides,
  };
}

describe("ChatTaskList actions", () => {
  afterEach(() => {
    cleanup();
  });

  it("opens stop, execute and delete actions from the overflow menu", async () => {
    const onTaskClick = vi.fn();
    const onTaskPause = vi.fn();
    const onTaskRun = vi.fn();
    const onTaskDelete = vi.fn();
    const task = taskJob();

    render(
      <ChatTaskList
        tasks={[task]}
        onTaskClick={onTaskClick}
        onTaskPause={onTaskPause}
        onTaskRun={onTaskRun}
        onTaskDelete={onTaskDelete}
      />,
    );

    expect(screen.queryByText("停止")).toBeNull();
    expect(screen.queryByText("执行")).toBeNull();
    expect(screen.queryByText("删除")).toBeNull();

    fireEvent.click(
      screen.getByRole("button", { name: "更多任务操作：每日巡检" }),
    );
    fireEvent.click(await screen.findByText("停止"));

    fireEvent.click(
      screen.getByRole("button", { name: "更多任务操作：每日巡检" }),
    );
    fireEvent.click(await screen.findByText("执行"));

    fireEvent.click(
      screen.getByRole("button", { name: "更多任务操作：每日巡检" }),
    );
    fireEvent.click(await screen.findByText("删除"));

    expect(onTaskPause).toHaveBeenCalledWith(task);
    expect(onTaskRun).toHaveBeenCalledWith(task);
    expect(onTaskDelete).toHaveBeenCalledWith(task);
    expect(onTaskClick).not.toHaveBeenCalled();
  });

  it("opens resume and delete actions for paused scheduled tasks", async () => {
    const onTaskResume = vi.fn();
    const task = taskJob({
      enabled: false,
      task: {
        visible_in_my_tasks: true,
        has_scheduled_result: false,
        latest_scheduled_preview: "",
        unread_execution_count: 0,
        is_running: false,
        is_paused: true,
        pause_reason: "manual",
      },
    });

    render(
      <ChatTaskList
        tasks={[task]}
        onTaskResume={onTaskResume}
        onTaskDelete={vi.fn()}
      />,
    );

    expect(screen.queryByRole("button", { name: "停止" })).toBeNull();
    expect(screen.queryByRole("button", { name: "执行" })).toBeNull();

    fireEvent.click(
      screen.getByRole("button", { name: "更多任务操作：每日巡检" }),
    );
    fireEvent.click(await screen.findByText("恢复"));

    await waitFor(() => {
      expect(screen.queryByText("停止")).toBeNull();
      expect(screen.queryByText("执行")).toBeNull();
    });

    expect(onTaskResume).toHaveBeenCalledWith(task);
  });
});
