import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { copy } from "./copy";

function restoreProperty(
  target: object,
  key: PropertyKey,
  descriptor?: PropertyDescriptor,
) {
  if (descriptor) {
    Object.defineProperty(target, key, descriptor);
    return;
  }
  delete (target as Record<PropertyKey, unknown>)[key];
}

describe("agentscope copy", () => {
  let clipboardDescriptor: PropertyDescriptor | undefined;
  let secureContextDescriptor: PropertyDescriptor | undefined;
  let permissionsPolicyDescriptor: PropertyDescriptor | undefined;
  let execCommandDescriptor: PropertyDescriptor | undefined;

  beforeEach(() => {
    clipboardDescriptor = Object.getOwnPropertyDescriptor(
      navigator,
      "clipboard",
    );
    secureContextDescriptor = Object.getOwnPropertyDescriptor(
      window,
      "isSecureContext",
    );
    permissionsPolicyDescriptor = Object.getOwnPropertyDescriptor(
      document,
      "permissionsPolicy",
    );
    execCommandDescriptor = Object.getOwnPropertyDescriptor(
      document,
      "execCommand",
    );
  });

  afterEach(() => {
    restoreProperty(navigator, "clipboard", clipboardDescriptor);
    restoreProperty(window, "isSecureContext", secureContextDescriptor);
    restoreProperty(
      document,
      "permissionsPolicy",
      permissionsPolicyDescriptor,
    );
    restoreProperty(document, "execCommand", execCommandDescriptor);
    vi.restoreAllMocks();
  });

  it("权限策略禁用 Clipboard API 时直接使用兼容复制", async () => {
    const writeText = vi.fn().mockRejectedValue(new Error("blocked"));
    const execCommand = vi.fn().mockReturnValue(true);

    Object.defineProperty(window, "isSecureContext", {
      configurable: true,
      value: true,
    });
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    Object.defineProperty(document, "permissionsPolicy", {
      configurable: true,
      value: {
        allowsFeature: vi.fn().mockReturnValue(false),
      },
    });
    Object.defineProperty(document, "execCommand", {
      configurable: true,
      value: execCommand,
    });

    await expect(copy('{"arg0":{}}')).resolves.toBeUndefined();

    expect(writeText).not.toHaveBeenCalled();
    expect(execCommand).toHaveBeenCalled();
    expect(execCommand.mock.calls[0]?.[0]).toBe("copy");
  });

  it("Clipboard API 失败后使用兼容复制", async () => {
    const writeText = vi.fn().mockRejectedValue(new Error("blocked"));
    const execCommand = vi.fn().mockReturnValue(true);

    Object.defineProperty(window, "isSecureContext", {
      configurable: true,
      value: true,
    });
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    Object.defineProperty(document, "execCommand", {
      configurable: true,
      value: execCommand,
    });

    await expect(copy("工具输入参数")).resolves.toBeUndefined();

    expect(writeText).toHaveBeenCalledWith("工具输入参数");
    expect(execCommand).toHaveBeenCalled();
  });

  it("所有复制方式失败时抛出错误", async () => {
    const execCommand = vi.fn().mockReturnValue(false);

    Object.defineProperty(window, "isSecureContext", {
      configurable: true,
      value: false,
    });
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: undefined,
    });
    Object.defineProperty(document, "execCommand", {
      configurable: true,
      value: execCommand,
    });

    await expect(copy("无法复制的内容")).rejects.toThrow("复制失败");
  });
});
