import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { FeedbackRecord } from "@/api/types/feedback";
import ResponseFeedbackCard from ".";

function makeFeedback(overrides: Partial<FeedbackRecord> = {}): FeedbackRecord {
  return {
    id: 1,
    feedback_content: "已反馈内容",
    feedback_options: ["输出格式需调整"],
    response_id: "response-1",
    trace_id: "trace-1",
    ...overrides,
  };
}

afterEach(() => {
  cleanup();
});

describe("ResponseFeedbackCard", () => {
  it("keeps submitted state during transient empty feedback for same response", () => {
    const { rerender } = render(
      <ResponseFeedbackCard
        chatId="chat-1"
        existingFeedback={makeFeedback()}
        responseId="response-1"
        sessionId="session-1"
        traceId="trace-1"
      />,
    );

    expect(screen.getByText(/反馈已收到/)).toBeInTheDocument();

    rerender(
      <ResponseFeedbackCard
        chatId="chat-1"
        existingFeedback={null}
        responseId="response-1"
        sessionId="session-1"
        traceId="trace-1"
      />,
    );

    expect(screen.getByText(/反馈已收到/)).toBeInTheDocument();
    expect(screen.queryByText("提交反馈")).not.toBeInTheDocument();
  });

  it("resets submitted state when rendering another response", () => {
    const { rerender } = render(
      <ResponseFeedbackCard
        chatId="chat-1"
        existingFeedback={makeFeedback()}
        responseId="response-1"
        sessionId="session-1"
        traceId="trace-1"
      />,
    );

    rerender(
      <ResponseFeedbackCard
        chatId="chat-1"
        existingFeedback={null}
        responseId="response-2"
        sessionId="session-1"
        traceId="trace-2"
      />,
    );

    expect(screen.queryByText(/反馈已收到/)).not.toBeInTheDocument();
    expect(screen.getByText("提交反馈")).toBeInTheDocument();
  });

  it("shows loading state instead of editable controls while feedback is loading", () => {
    render(
      <ResponseFeedbackCard
        chatId="chat-1"
        existingFeedback={null}
        loadingExisting
        responseId="response-1"
        sessionId="session-1"
        traceId="trace-1"
      />,
    );

    expect(screen.getByText("正在加载历史反馈...")).toBeInTheDocument();
    expect(screen.queryByText("提交反馈")).not.toBeInTheDocument();
  });
});
