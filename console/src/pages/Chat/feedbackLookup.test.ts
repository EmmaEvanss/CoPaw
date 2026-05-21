import { describe, expect, it } from "vitest";
import type { FeedbackRecord } from "@/api/types/feedback";
import {
  buildFeedbackLookup,
  findFeedbackForResponse,
} from "./feedbackLookup";
import type { ChatRuntimeResponseCardData } from "./messageMeta";

function makeFeedback(
  overrides: Partial<FeedbackRecord> = {},
): FeedbackRecord {
  return {
    id: 1,
    feedback_content: "建议补充结论",
    feedback_options: ["其他想法"],
    ...overrides,
  };
}

describe("feedback lookup", () => {
  it("matches session feedback by response id first", () => {
    const feedback = makeFeedback({
      response_id: "assistant-message-1",
      trace_id: "trace-1",
    });
    const lookup = buildFeedbackLookup([feedback]);

    const response = {
      id: "runtime-card-1",
      output: [{ role: "assistant", id: "assistant-message-1" }],
    } as unknown as ChatRuntimeResponseCardData;

    expect(findFeedbackForResponse(lookup, response)).toBe(feedback);
  });

  it("does not use runtime msg id as feedback response id", () => {
    const feedback = makeFeedback({
      response_id: "msg_runtime_should_not_match",
      trace_id: "trace-runtime-1",
    });
    const lookup = buildFeedbackLookup([feedback]);

    const response = {
      id: "response_runtime_should_not_match",
      output: [
        {
          role: "assistant",
          id: "msg_runtime_should_not_match",
          trace_id: "trace-runtime-1",
        },
      ],
    } as unknown as ChatRuntimeResponseCardData;

    expect(findFeedbackForResponse(lookup, response)).toBe(feedback);
  });

  it("does not match stale runtime msg id without trace", () => {
    const feedback = makeFeedback({
      response_id: "msg_stale_runtime_id",
      trace_id: null,
    });
    const lookup = buildFeedbackLookup([feedback]);

    const response = {
      id: "response_current_runtime_id",
      output: [
        {
          role: "assistant",
          id: "msg_stale_runtime_id",
        },
      ],
    } as unknown as ChatRuntimeResponseCardData;

    expect(findFeedbackForResponse(lookup, response)).toBeNull();
  });

  it("uses trace id as a stable response id fallback", () => {
    const feedback = makeFeedback({
      response_id: "trace-response-fallback",
      trace_id: "trace-response-fallback",
    });
    const lookup = buildFeedbackLookup([feedback]);

    const response = {
      id: "response_runtime_id",
      output: [
        {
          role: "assistant",
          id: "msg_runtime_id",
          metadata: { trace_id: "trace-response-fallback" },
        },
      ],
    } as unknown as ChatRuntimeResponseCardData;

    expect(findFeedbackForResponse(lookup, response)).toBe(feedback);
  });

  it("matches session feedback by stable original id instead of runtime msg id", () => {
    const feedback = makeFeedback({
      response_id: "stable-output-1",
      trace_id: "trace-stable-1",
    });
    const lookup = buildFeedbackLookup([feedback]);

    const response = {
      id: "runtime-card-stable-1",
      output: [
        {
          role: "assistant",
          id: "msg_runtime_changed_after_reload",
          metadata: { original_id: "stable-output-1" },
        },
      ],
    } as unknown as ChatRuntimeResponseCardData;

    expect(findFeedbackForResponse(lookup, response)).toBe(feedback);
  });

  it("matches session feedback by nested stable original id", () => {
    const feedback = makeFeedback({
      response_id: "stable-output-2",
      trace_id: "trace-stable-2",
    });
    const lookup = buildFeedbackLookup([feedback]);

    const response = {
      id: "runtime-card-stable-2",
      output: [
        {
          role: "assistant",
          id: "msg_runtime_changed_again",
          metadata: { metadata: { original_id: "stable-output-2" } },
        },
      ],
    } as unknown as ChatRuntimeResponseCardData;

    expect(findFeedbackForResponse(lookup, response)).toBe(feedback);
  });

  it("matches session feedback by trace id when response id is absent", () => {
    const feedback = makeFeedback({
      response_id: null,
      trace_id: "trace-2",
    });
    const lookup = buildFeedbackLookup([feedback]);

    const response = {
      id: "runtime-card-2",
      output: [
        {
          role: "assistant",
          id: "assistant-message-2",
          metadata: { trace_id: "trace-2" },
        },
      ],
    } as unknown as ChatRuntimeResponseCardData;

    expect(findFeedbackForResponse(lookup, response)).toBe(feedback);
  });

  it("matches session feedback when trace id is stored on output message", () => {
    const feedback = makeFeedback({
      response_id: null,
      trace_id: "trace-3",
    });
    const lookup = buildFeedbackLookup([feedback]);

    const response = {
      id: "runtime-card-3",
      output: [
        {
          role: "assistant",
          id: "assistant-message-3",
          trace_id: "trace-3",
        },
      ],
    } as unknown as ChatRuntimeResponseCardData;

    expect(findFeedbackForResponse(lookup, response)).toBe(feedback);
  });

  it("matches session feedback when trace id is stored in nested metadata", () => {
    const feedback = makeFeedback({
      response_id: null,
      trace_id: "trace-4",
    });
    const lookup = buildFeedbackLookup([feedback]);

    const response = {
      id: "runtime-card-4",
      output: [
        {
          role: "assistant",
          id: "assistant-message-4",
          metadata: { metadata: { trace_id: "trace-4" } },
        },
      ],
    } as unknown as ChatRuntimeResponseCardData;

    expect(findFeedbackForResponse(lookup, response)).toBe(feedback);
  });

  it("does not infer feedback from nearby time when history id is unmatched", () => {
    const feedback = makeFeedback({
      response_id: "635460b8-5b46-413d-a662-4a7484e16b37",
      trace_id: "635460b8-5b46-413d-a662-4a7484e16b37",
      updated_at: "2026-05-20T22:08:35",
    });
    const lookup = buildFeedbackLookup([feedback]);

    const response = {
      id: "response_history",
      output: [
        {
          role: "assistant",
          id: "msg_history_runtime",
          metadata: {
            original_id: "jT5wrVekXy3aQqg4rGB5Yg",
            metadata: {},
          },
          timestamp: "2026-05-20T22:08:16.116",
        },
      ],
    } as unknown as ChatRuntimeResponseCardData;

    expect(findFeedbackForResponse(lookup, response)).toBeNull();
  });

  it("does not match a newer live response by nearby previous feedback time", () => {
    const feedback = makeFeedback({
      response_id: "previous-trace",
      trace_id: "previous-trace",
      updated_at: "2026-05-20T22:25:30",
    });
    const lookup = buildFeedbackLookup([feedback]);

    const response = {
      id: "response_live",
      trace_id: "new-response-trace",
      output: [
        {
          role: "assistant",
          id: "msg_live",
          metadata: { trace_id: "new-response-trace" },
          timestamp: "2026-05-20T22:26:00",
        },
      ],
    } as unknown as ChatRuntimeResponseCardData;

    expect(findFeedbackForResponse(lookup, response)).toBeNull();
  });

  it("does not match history by time when feedback happened before response", () => {
    const feedback = makeFeedback({
      response_id: "previous-trace",
      trace_id: "previous-trace",
      updated_at: "2026-05-20T22:25:30",
    });
    const lookup = buildFeedbackLookup([feedback]);

    const response = {
      id: "response_history_after_feedback",
      output: [
        {
          role: "assistant",
          id: "msg_history_after_feedback",
          metadata: { original_id: "stable-history-id" },
          timestamp: "2026-05-20T22:26:00",
        },
      ],
    } as unknown as ChatRuntimeResponseCardData;

    expect(findFeedbackForResponse(lookup, response)).toBeNull();
  });

  it("does not mark an unreviewed middle response without session responses", () => {
    const firstFeedback = makeFeedback({
      id: 1,
      response_id: "first-trace",
      trace_id: "first-trace",
      updated_at: "2026-05-20T22:57:10",
    });
    const thirdFeedback = makeFeedback({
      id: 3,
      response_id: "third-trace",
      trace_id: "third-trace",
      updated_at: "2026-05-20T22:57:30",
    });
    const lookup = buildFeedbackLookup([firstFeedback, thirdFeedback]);

    const response = {
      id: "middle-response",
      output: [
        {
          role: "assistant",
          id: "msg_middle_runtime",
          metadata: {
            original_id: "middle-original",
          },
          timestamp: "2026-05-20T22:57:20",
        },
      ],
    } as unknown as ChatRuntimeResponseCardData;

    expect(findFeedbackForResponse(lookup, response)).toBeNull();
  });

  it("assigns nearby feedback by session response time without marking neighbors", () => {
    const firstFeedback = makeFeedback({
      id: 11,
      response_id: "first-trace",
      trace_id: "first-trace",
      updated_at: "2026-05-20T22:57:10",
    });
    const thirdFeedback = makeFeedback({
      id: 33,
      response_id: "third-trace",
      trace_id: "third-trace",
      updated_at: "2026-05-20T22:57:55",
    });

    const firstResponse = {
      output: [
        {
          role: "assistant",
          id: "msg_first_runtime",
          metadata: { original_id: "first-original" },
          timestamp: "2026-05-20T22:57:05",
        },
      ],
    } as unknown as ChatRuntimeResponseCardData;
    const middleResponse = {
      output: [
        {
          role: "assistant",
          id: "msg_middle_runtime",
          metadata: { original_id: "middle-original" },
          timestamp: "2026-05-20T22:57:20",
        },
      ],
    } as unknown as ChatRuntimeResponseCardData;
    const thirdResponse = {
      output: [
        {
          role: "assistant",
          id: "msg_third_runtime",
          metadata: { original_id: "third-original" },
          timestamp: "2026-05-20T22:57:50",
        },
      ],
    } as unknown as ChatRuntimeResponseCardData;
    const lookup = buildFeedbackLookup(
      [firstFeedback, thirdFeedback],
      [firstResponse, middleResponse, thirdResponse],
    );

    expect(findFeedbackForResponse(lookup, firstResponse)).toBe(firstFeedback);
    expect(findFeedbackForResponse(lookup, middleResponse)).toBeNull();
    expect(findFeedbackForResponse(lookup, thirdResponse)).toBe(thirdFeedback);
  });
});
