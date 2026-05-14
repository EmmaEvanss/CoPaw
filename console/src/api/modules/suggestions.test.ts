import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  fetchBackendSuggestions,
  fetchGeneratedSuggestions,
  fetchQAContent,
} from "./suggestions";

describe("suggestions api", () => {
  beforeEach(() => {
    window.__env__ = { baseUrl: "" };
    vi.restoreAllMocks();
    vi.stubGlobal("localStorage", {
      getItem: vi.fn(() => null),
      setItem: vi.fn(),
      removeItem: vi.fn(),
    });
    vi.stubGlobal("sessionStorage", {
      getItem: vi.fn(() => null),
      setItem: vi.fn(),
      removeItem: vi.fn(),
    });
    vi.useRealTimers();
  });

  it("normalizes backend suggestions from the first stored entry", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        suggestions: [
          {
            id: "suggestion-1",
            suggestions: [" 问题一 ", "", 1, "问题二"],
          },
        ],
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      fetchBackendSuggestions({ sessionId: "session-1" }),
    ).resolves.toEqual(["问题一", "问题二"]);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/console/suggestions?session_id=session-1",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("returns restored mock suggestions when generated API mock mode is enabled", async () => {
    vi.useFakeTimers();

    const promise = fetchGeneratedSuggestions({
      chatId: "chat-1",
      turnId: "turn-1",
      userMessage: "帮我分析这个任务",
      assistantMessage: "分析完成",
    });
    await vi.advanceTimersByTimeAsync(500);

    await expect(promise).resolves.toEqual([
      "关于“帮我分析这个任务”能展开吗",
      "能给我一个执行建议吗",
      "还有哪些补充信息",
    ]);
  });

  it("posts chat id and user message when fetching Q&A content", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        success: true,
        qa_content: {
          user_message: "用户问题",
          assistant_response: "助手回答",
        },
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      fetchQAContent({ chatId: "chat-1", userMessage: "用户问题" }),
    ).resolves.toEqual({
      success: true,
      qa_content: {
        user_message: "用户问题",
        assistant_response: "助手回答",
      },
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/console/suggestions/qa-content",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          chat_id: "chat-1",
          user_message: "用户问题",
        }),
      }),
    );
  });
});
