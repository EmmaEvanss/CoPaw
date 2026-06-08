import { afterEach, describe, expect, it, vi } from "vitest";

import {
  CURRENT_SOURCE_SYSTEM_CONFIG_SWITCHES,
  readCronUnreadAutoPauseConfig,
  validateSourceSystemConfig,
  writeCronUnreadAutoPauseValue,
  writeRegisteredSwitchValue,
  writeToolResultCompactValue,
} from "./registry";

describe("SystemConfigPage registry compatibility", () => {
  const originalStructuredClone = globalThis.structuredClone;

  afterEach(() => {
    vi.unstubAllGlobals();
    if (originalStructuredClone) {
      globalThis.structuredClone = originalStructuredClone;
    } else {
      delete (globalThis as typeof globalThis & { structuredClone?: unknown })
        .structuredClone;
    }
  });

  it("writes switch values without requiring native structuredClone", () => {
    vi.stubGlobal("structuredClone", undefined);
    const source = {
      provider_policy: { default_model: "qwen-max" },
    };

    const next = writeRegisteredSwitchValue(
      source,
      CURRENT_SOURCE_SYSTEM_CONFIG_SWITCHES[0],
      false,
    );

    expect(next).toEqual({
      provider_policy: { default_model: "qwen-max" },
      feature_switches: { chat_task_progress_enabled: false },
    });
    expect(source).toEqual({
      provider_policy: { default_model: "qwen-max" },
    });
  });

  it("preserves nested tool config keys without native structuredClone", () => {
    vi.stubGlobal("structuredClone", undefined);
    const source = {
      tool_result_compact: {
        recent_max_bytes: 12000,
        unknown_retained: "yes",
      },
    };

    const next = writeToolResultCompactValue(source, "recent_max_bytes", 16000);

    expect(next).toEqual({
      tool_result_compact: {
        recent_max_bytes: 16000,
        unknown_retained: "yes",
      },
    });
    expect(source.tool_result_compact.recent_max_bytes).toBe(12000);
  });

  it("reads default cron unread auto pause settings", () => {
    expect(readCronUnreadAutoPauseConfig({})).toEqual({
      enabled: true,
      threshold: 10,
    });
  });

  it("writes cron unread auto pause settings without mutating source", () => {
    vi.stubGlobal("structuredClone", undefined);
    const source = {
      provider_policy: { default_model: "qwen-max" },
      cron_unread_auto_pause: {
        enabled: true,
      },
    };

    const next = writeCronUnreadAutoPauseValue(source, "threshold", 12);

    expect(next).toEqual({
      provider_policy: { default_model: "qwen-max" },
      cron_unread_auto_pause: {
        enabled: true,
        threshold: 12,
      },
    });
    expect(source.cron_unread_auto_pause).toEqual({
      enabled: true,
    });
  });

  it("rejects invalid cron unread auto pause threshold", () => {
    expect(
      validateSourceSystemConfig({
        cron_unread_auto_pause: {
          enabled: true,
          threshold: 0,
        },
      }),
    ).toContain("1");
  });
});
