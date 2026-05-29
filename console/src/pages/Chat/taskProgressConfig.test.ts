import { describe, expect, it } from "vitest";

import { isChatTaskProgressEnabled } from "./taskProgressConfig";

describe("isChatTaskProgressEnabled", () => {
  it("defaults to enabled when config is missing", () => {
    expect(isChatTaskProgressEnabled(null)).toBe(true);
  });

  it("reads explicit false from effective source config", () => {
    expect(
      isChatTaskProgressEnabled({
        source_id: "portal",
        version: 1,
        is_default: false,
        stale: false,
        config: {
          feature_switches: {
            chat_task_progress_enabled: false,
          },
        },
      }),
    ).toBe(false);
  });

  it("treats string false as disabled for dirty config compatibility", () => {
    expect(
      isChatTaskProgressEnabled({
        source_id: "portal",
        version: 1,
        is_default: false,
        stale: false,
        config: {
          feature_switches: {
            chat_task_progress_enabled: "false",
          },
        },
      }),
    ).toBe(false);
  });
});
