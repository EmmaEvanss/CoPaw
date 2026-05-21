import { beforeEach, describe, expect, it, vi } from "vitest";
import { useSourceSystemConfigStore } from "./sourceSystemConfigStore";
import { sourceSystemConfigApi } from "../api/modules/sourceSystemConfig";

vi.mock("../api/modules/sourceSystemConfig", () => ({
  sourceSystemConfigApi: {
    getEffective: vi.fn(),
  },
}));

describe("sourceSystemConfigStore", () => {
  beforeEach(() => {
    useSourceSystemConfigStore.setState({
      config: null,
      sourceId: null,
      loading: false,
      error: null,
      requestSeq: 0,
    });
    vi.clearAllMocks();
  });

  it("loads effective source config", async () => {
    vi.mocked(sourceSystemConfigApi.getEffective).mockResolvedValue({
      source_id: "portal",
      version: 1,
      is_default: false,
      stale: false,
      config: {
        provider_policy: { default_model: "qwen-max" },
      },
    });

    await useSourceSystemConfigStore.getState().loadEffectiveConfig("portal");

    expect(useSourceSystemConfigStore.getState().sourceId).toBe("portal");
    expect(useSourceSystemConfigStore.getState().config?.config).toEqual({
      provider_policy: { default_model: "qwen-max" },
    });
  });

  it("ignores stale response from previous source", async () => {
    let resolveFirst!: (value: any) => void;
    vi.mocked(sourceSystemConfigApi.getEffective)
      .mockReturnValueOnce(
        new Promise((resolve) => {
          resolveFirst = resolve;
        }),
      )
      .mockResolvedValueOnce({
        source_id: "source-b",
        version: 2,
        is_default: false,
        stale: false,
        config: {
          source_name: "source-b",
        },
      });

    const first = useSourceSystemConfigStore
      .getState()
      .loadEffectiveConfig("source-a");
    const second = useSourceSystemConfigStore
      .getState()
      .loadEffectiveConfig("source-b");
    resolveFirst({
      source_id: "source-a",
      version: 1,
      is_default: false,
      stale: false,
      config: {
        source_name: "source-a",
      },
    });

    await Promise.all([first, second]);

    expect(useSourceSystemConfigStore.getState().sourceId).toBe("source-b");
    expect(useSourceSystemConfigStore.getState().config?.config).toEqual({
      source_name: "source-b",
    });
  });
});
