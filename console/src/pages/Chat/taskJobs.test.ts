import { describe, expect, it } from "vitest";
import type { CronJobSpecOutput } from "../../api/types";
import { getTaskSidebarMeta } from "./taskJobs";

function taskJob(
  overrides: Partial<CronJobSpecOutput> = {},
): CronJobSpecOutput {
  return {
    id: "job-1",
    name: "定时任务",
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

describe("getTaskSidebarMeta", () => {
  it("allows stopping, executing and deleting active scheduled tasks", () => {
    const meta = getTaskSidebarMeta(taskJob());

    expect(meta.state).toBe("active");
    expect(meta.canPause).toBe(true);
    expect(meta.canRun).toBe(true);
    expect(meta.canResume).toBe(false);
    expect(meta.canDelete).toBe(true);
  });

  it("allows resuming and deleting paused scheduled tasks", () => {
    const meta = getTaskSidebarMeta(
      taskJob({
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
      }),
    );

    expect(meta.state).toBe("manual-paused");
    expect(meta.canPause).toBe(false);
    expect(meta.canRun).toBe(false);
    expect(meta.canResume).toBe(true);
    expect(meta.canDelete).toBe(true);
  });

  it("hides mutation actions while a task is running", () => {
    const meta = getTaskSidebarMeta(
      taskJob({
        task: {
          visible_in_my_tasks: true,
          has_scheduled_result: false,
          latest_scheduled_preview: "",
          unread_execution_count: 0,
          is_running: true,
          is_paused: false,
          pause_reason: null,
        },
      }),
    );

    expect(meta.state).toBe("running");
    expect(meta.canPause).toBe(false);
    expect(meta.canRun).toBe(false);
    expect(meta.canResume).toBe(false);
    expect(meta.canDelete).toBe(false);
  });
});
