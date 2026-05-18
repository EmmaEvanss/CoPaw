import { beforeEach, describe, expect, it, vi } from "vitest";

import { buildAuthHeaders } from "./authHeaders";
import { useIframeStore } from "../stores/iframeStore";

interface CustomWindow extends Window {
  currentUserId?: string;
}

vi.mock("./config", () => ({
  getApiToken: vi.fn(() => ""),
}));

vi.mock("./externalToken", () => ({
  getExternalToken: vi.fn(() => ""),
  isExternalTokenEnabled: vi.fn(() => false),
}));

describe("buildAuthHeaders", () => {
  beforeEach(() => {
    sessionStorage.clear();
    useIframeStore.getState().clearContext();
    delete (window as CustomWindow).currentUserId;
  });

  it("独立访问时也会携带默认 source 头", () => {
    expect(buildAuthHeaders()).toMatchObject({
      "X-User-Id": "default",
      "X-Tenant-Id": "default",
      "X-Source-Id": "default",
    });
  });

  it("iframe source 会覆盖默认 source", () => {
    useIframeStore.getState().setContext({ source: "rmassist" });

    expect(buildAuthHeaders()["X-Source-Id"]).toBe("rmassist");
  });
});
