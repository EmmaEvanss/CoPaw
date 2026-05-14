import React from "react";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import useSuggestionsPolling from "./useSuggestionsPolling";
import type { CurrentQARef } from "./currentQARef";

const mocks = vi.hoisted(() => ({
  sessionsContext: {},
  fetchBackendSuggestions: vi.fn(),
  fetchGeneratedSuggestions: vi.fn(),
  fetchQAContent: vi.fn(),
  getSessionList: vi.fn(),
  getChatIdForSession: vi.fn(),
  getRealIdForSession: vi.fn(),
  updateMessage: vi.fn(),
}));

vi.mock("@/api/modules/suggestions", () => ({
  fetchBackendSuggestions: mocks.fetchBackendSuggestions,
  fetchGeneratedSuggestions: mocks.fetchGeneratedSuggestions,
  fetchQAContent: mocks.fetchQAContent,
}));

vi.mock("use-context-selector", () => ({
  createContext: vi.fn(() => ({})),
  useContextSelector: (
    context: unknown,
    selector: (value: unknown) => unknown,
  ) => {
    if (context === mocks.sessionsContext) {
      return selector({ currentSessionId: "session-1" });
    }
    return selector({});
  },
}));

vi.mock("../../Context/ChatAnywhereSessionsContext", () => ({
  ChatAnywhereSessionsContext: mocks.sessionsContext,
}));

vi.mock("../../Context/ChatAnywhereOptionsContext", () => ({
  useChatAnywhereOptions: (selector: (value: unknown) => unknown) =>
    selector({
      session: {
        api: {
          getSessionList: mocks.getSessionList,
          getChatIdForSession: mocks.getChatIdForSession,
          getRealIdForSession: mocks.getRealIdForSession,
        },
      },
    }),
}));

let hookApi: ReturnType<typeof useSuggestionsPolling>;
let root: Root | undefined;
let container: HTMLDivElement | undefined;

function createCurrentQARef(): CurrentQARef {
  return {
    current: {
      request: {
        cards: [
          {
            data: {
              input: [
                {
                  content: [{ type: "text", text: "用户问题" }],
                },
              ],
            },
          },
        ],
      },
      response: {
        id: "response-1",
        role: "assistant",
        cards: [
          {
            data: {
              id: "response-1",
              output: [
                {
                  id: "message-1",
                  role: "assistant",
                  type: "message",
                  content: [{ type: "text", text: "助手回答" }],
                },
              ],
            },
          },
        ],
      },
    },
  } as CurrentQARef;
}

function Harness(props: { currentQARef: CurrentQARef }) {
  hookApi = useSuggestionsPolling({
    currentQARef: props.currentQARef,
    updateMessage: mocks.updateMessage,
  });
  return null;
}

function renderHarness(currentQARef: CurrentQARef) {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  act(() => {
    root?.render(<Harness currentQARef={currentQARef} />);
  });
}

describe("useSuggestionsPolling", () => {
  beforeEach(() => {
    mocks.fetchBackendSuggestions.mockReset();
    mocks.fetchGeneratedSuggestions.mockReset();
    mocks.fetchQAContent.mockReset();
    mocks.getSessionList.mockReset();
    mocks.getChatIdForSession.mockReset();
    mocks.getRealIdForSession.mockReset();
    mocks.updateMessage.mockReset();
    mocks.getChatIdForSession.mockReturnValue("chat-1");
    mocks.getRealIdForSession.mockReturnValue("real-session-1");
    mocks.getSessionList.mockResolvedValue(undefined);
  });

  afterEach(() => {
    act(() => {
      root?.unmount();
    });
    container?.remove();
    root = undefined;
    container = undefined;
  });

  it("uses backend suggestions first when available", async () => {
    const currentQARef = createCurrentQARef();
    mocks.fetchBackendSuggestions.mockResolvedValue(["后端问题"]);

    renderHarness(currentQARef);

    await act(async () => {
      await hookApi.pollSuggestions();
    });

    expect(mocks.fetchBackendSuggestions).toHaveBeenCalledWith({
      sessionId: "session-1",
    });
    expect(mocks.fetchQAContent).not.toHaveBeenCalled();
    expect(mocks.fetchGeneratedSuggestions).not.toHaveBeenCalled();
    expect(currentQARef.current.response?.cards?.[0]?.data.suggestions).toEqual(
      ["后端问题"],
    );
    expect(mocks.updateMessage).toHaveBeenCalledWith(
      currentQARef.current.response,
    );
  });

  it("falls back to backend Q&A content and generated suggestions", async () => {
    const currentQARef = createCurrentQARef();
    mocks.fetchBackendSuggestions.mockResolvedValue([]);
    mocks.fetchQAContent.mockResolvedValue({
      success: true,
      qa_content: {
        user_message: "提取后的问题",
        assistant_response: "提取后的回答",
      },
    });
    mocks.fetchGeneratedSuggestions.mockResolvedValue(["兜底问题"]);

    renderHarness(currentQARef);

    await act(async () => {
      await hookApi.pollSuggestions();
    });

    expect(mocks.fetchQAContent).toHaveBeenCalledWith({
      chatId: "chat-1",
      userMessage: "用户问题",
    });
    expect(mocks.fetchGeneratedSuggestions).toHaveBeenCalledWith({
      chatId: "chat-1",
      turnId: "response-1",
      userMessage: "提取后的问题",
      assistantMessage: "提取后的回答",
    });
    expect(currentQARef.current.response?.cards?.[0]?.data.suggestions).toEqual(
      ["兜底问题"],
    );
  });

  it("uses local assistant text when Q&A content is unavailable", async () => {
    const currentQARef = createCurrentQARef();
    mocks.fetchBackendSuggestions.mockResolvedValue([]);
    mocks.fetchQAContent.mockResolvedValue({ success: false });
    mocks.fetchGeneratedSuggestions.mockResolvedValue(["本地兜底问题"]);

    renderHarness(currentQARef);

    await act(async () => {
      await hookApi.pollSuggestions();
    });

    expect(mocks.fetchGeneratedSuggestions).toHaveBeenCalledWith({
      chatId: "chat-1",
      turnId: "response-1",
      userMessage: "用户问题",
      assistantMessage: "助手回答",
    });
    expect(currentQARef.current.response?.cards?.[0]?.data.suggestions).toEqual(
      ["本地兜底问题"],
    );
  });
});
