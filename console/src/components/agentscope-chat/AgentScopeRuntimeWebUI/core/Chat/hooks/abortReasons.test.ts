import { describe, expect, it } from "vitest";
import {
  createChatStreamAbortReason,
  getChatStreamAbortMessage,
  isAbortLikeError,
  shouldStopBackendForFetchAbort,
} from "./abortReasons";

describe("chat stream abort reasons", () => {
  it("treats navigation detach aborts as client-only stream aborts", () => {
    const controller = new AbortController();
    const reason = createChatStreamAbortReason("detach");

    controller.abort(reason);

    expect(isAbortLikeError(controller.signal.reason)).toBe(true);
    expect(
      shouldStopBackendForFetchAbort(
        controller.signal.reason,
        controller.signal,
      ),
    ).toBe(false);
  });

  it("treats timeout aborts as backend stop requests", () => {
    const controller = new AbortController();
    const reason = createChatStreamAbortReason("timeout", "timed out");

    controller.abort(reason);

    expect(isAbortLikeError(controller.signal.reason)).toBe(true);
    expect(
      shouldStopBackendForFetchAbort(
        controller.signal.reason,
        controller.signal,
      ),
    ).toBe(true);
    expect(getChatStreamAbortMessage(controller.signal.reason)).toBe(
      "timed out",
    );
  });

  it("does not stop the backend for plain AbortError unless the signal reason is timeout", () => {
    const controller = new AbortController();
    controller.abort(createChatStreamAbortReason("detach"));

    expect(
      shouldStopBackendForFetchAbort(
        new DOMException("The operation was aborted.", "AbortError"),
        controller.signal,
      ),
    ).toBe(false);
  });
});
