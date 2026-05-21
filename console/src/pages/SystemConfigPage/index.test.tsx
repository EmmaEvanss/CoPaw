import React from "react";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import SystemConfigPage from "./index";
import { useIframeStore } from "@/stores/iframeStore";
import { useSourceSystemConfigStore } from "@/stores/sourceSystemConfigStore";

const mocks = vi.hoisted(() => ({
  sourceSystemConfigApi: {
    getCurrent: vi.fn(),
    updateCurrent: vi.fn(),
    deleteCurrent: vi.fn(),
  },
  messageApi: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

vi.mock("@/api/modules/sourceSystemConfig", () => ({
  sourceSystemConfigApi: mocks.sourceSystemConfigApi,
}));

vi.mock("@/hooks/useAppMessage", () => ({
  useAppMessage: () => ({
    message: mocks.messageApi,
  }),
}));

describe("SystemConfigPage", () => {
  const loadEffectiveConfig = vi.fn().mockResolvedValue(undefined);

  function createDeferred<T>() {
    let resolve!: (value: T) => void;
    let reject!: (reason?: unknown) => void;
    const promise = new Promise<T>((nextResolve, nextReject) => {
      resolve = nextResolve;
      reject = nextReject;
    });
    return { promise, resolve, reject };
  }

  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.clearAllMocks();
    useIframeStore.getState().clearContext();
    useIframeStore.getState().setContext({
      source: "portal",
      manager: true,
    });
    useSourceSystemConfigStore.setState({
      config: null,
      sourceId: null,
      loading: false,
      error: null,
      requestSeq: 0,
      loadEffectiveConfig,
    });
    mocks.sourceSystemConfigApi.getCurrent.mockResolvedValue({
      source_id: "portal",
      config: {},
      version: 0,
      is_default: true,
      updated_by: null,
      updated_at: null,
    });
  });

  it("renders 403 state for non-manager access", async () => {
    useIframeStore.getState().setContext({
      manager: false,
      isSuperManager: false,
    });

    render(<SystemConfigPage />);

    expect(await screen.findByText("403")).toBeTruthy();
    expect(
      screen.getByText("仅管理员可访问当前 Source 系统配置页面。"),
    ).toBeTruthy();
    expect(mocks.sourceSystemConfigApi.getCurrent).not.toHaveBeenCalled();
  });

  it("loads current-source config and saves switch changes", async () => {
    mocks.sourceSystemConfigApi.updateCurrent.mockResolvedValue({
      source_id: "portal",
      config: {
        feature_switches: {
          chat_task_progress_enabled: false,
        },
      },
      version: 1,
      is_default: false,
      updated_by: "alice",
      updated_at: "2026-05-20 22:00:00",
    });

    render(<SystemConfigPage />);

    await waitFor(() => {
      expect(screen.queryAllByText("继承默认值").length).toBeGreaterThan(0);
    });

    fireEvent.click(screen.getByRole("switch"));
    fireEvent.click(screen.getByRole("button", { name: "common.save" }));

    await waitFor(() => {
      expect(mocks.sourceSystemConfigApi.updateCurrent).toHaveBeenCalledWith({
        config: {
          feature_switches: {
            chat_task_progress_enabled: false,
          },
        },
      });
    });
    expect(loadEffectiveConfig).toHaveBeenCalledWith("portal");
    expect(mocks.messageApi.success).toHaveBeenCalled();
  });

  it("deletes explicit config and refreshes effective config", async () => {
    mocks.sourceSystemConfigApi.getCurrent
      .mockResolvedValueOnce({
        source_id: "portal",
        config: {
          feature_switches: {
            chat_task_progress_enabled: false,
          },
        },
        version: 2,
        is_default: false,
        updated_by: "alice",
        updated_at: "2026-05-20 22:00:00",
      })
      .mockResolvedValueOnce({
        source_id: "portal",
        config: {},
        version: 0,
        is_default: true,
        updated_by: null,
        updated_at: null,
      });
    mocks.sourceSystemConfigApi.deleteCurrent.mockResolvedValue({
      deleted: true,
    });

    render(<SystemConfigPage />);

    expect(await screen.findByText("存在显式覆盖")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "common.delete" }));

    await waitFor(() => {
      expect(mocks.sourceSystemConfigApi.deleteCurrent).toHaveBeenCalledTimes(1);
    });
    expect(loadEffectiveConfig).toHaveBeenCalledWith("portal");
    expect(await screen.findByText("继承默认值")).toBeTruthy();
  });

  it("clears stale draft and blocks save when the next source load fails", async () => {
    mocks.sourceSystemConfigApi.getCurrent
      .mockResolvedValueOnce({
        source_id: "portal",
        config: {
          feature_switches: {
            chat_task_progress_enabled: false,
          },
        },
        version: 2,
        is_default: false,
        updated_by: "alice",
        updated_at: "2026-05-20 22:00:00",
      })
      .mockRejectedValueOnce(new Error("retail load failed"));

    render(<SystemConfigPage />);

    await waitFor(() => {
      expect(screen.getByRole("switch")).toHaveAttribute(
        "aria-checked",
        "false",
      );
    });

    act(() => {
      useIframeStore.getState().setContext({
        source: "retail",
      });
    });

    expect(await screen.findByText("当前 Source 配置加载失败")).toBeTruthy();
    expect(screen.getByRole("switch")).toHaveAttribute(
      "aria-checked",
      "true",
    );
    expect(
      screen.getByRole("button", { name: "common.save" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "common.delete" }),
    ).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "common.save" }));
    expect(mocks.sourceSystemConfigApi.updateCurrent).not.toHaveBeenCalled();
  });

  it("ignores stale save responses after switching to another source", async () => {
    const saveDeferred = createDeferred<{
      source_id: string;
      config: Record<string, unknown>;
      version: number;
      is_default: boolean;
      updated_by: string | null;
      updated_at: string | null;
    }>();
    mocks.sourceSystemConfigApi.getCurrent
      .mockResolvedValueOnce({
        source_id: "portal",
        config: {
          feature_switches: {
            chat_task_progress_enabled: false,
          },
        },
        version: 1,
        is_default: false,
        updated_by: "alice",
        updated_at: "2026-05-20 22:00:00",
      })
      .mockResolvedValueOnce({
        source_id: "retail",
        config: {},
        version: 0,
        is_default: true,
        updated_by: null,
        updated_at: null,
      });
    mocks.sourceSystemConfigApi.updateCurrent.mockReturnValueOnce(
      saveDeferred.promise,
    );

    render(<SystemConfigPage />);

    await waitFor(() => {
      expect(screen.getByRole("switch")).toHaveAttribute(
        "aria-checked",
        "false",
      );
    });

    fireEvent.click(screen.getByRole("button", { name: "common.save" }));

    act(() => {
      useIframeStore.getState().setContext({
        source: "retail",
      });
    });

    await waitFor(() => {
      expect(screen.getAllByText("retail").length).toBeGreaterThan(0);
      expect(screen.getByRole("switch")).toHaveAttribute(
        "aria-checked",
        "true",
      );
    });

    await act(async () => {
      saveDeferred.resolve({
        source_id: "portal",
        config: {
          feature_switches: {
            chat_task_progress_enabled: false,
          },
        },
        version: 2,
        is_default: false,
        updated_by: "alice",
        updated_at: "2026-05-21 10:00:00",
      });
      await saveDeferred.promise;
    });

    await waitFor(() => {
      expect(screen.getAllByText("retail").length).toBeGreaterThan(0);
      expect(screen.getByRole("switch")).toHaveAttribute(
        "aria-checked",
        "true",
      );
    });
    expect(loadEffectiveConfig).not.toHaveBeenCalledWith("portal");
  });
});
