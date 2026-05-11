import {
  fetchBackendSuggestions,
  fetchGeneratedSuggestions,
  fetchQAContent,
  type QAContentResponse,
} from "@/api/modules/suggestions";
import {
  extractCopyableText,
  extractUserMessageText,
} from "@/pages/Chat/utils";
import { useCallback, useRef, useEffect } from "react";
import { useContextSelector } from "use-context-selector";
import { ChatAnywhereSessionsContext } from "../../Context/ChatAnywhereSessionsContext";
import { useChatAnywhereOptions } from "../../Context/ChatAnywhereOptionsContext";

/**
 * 猜你想问建议获取 Hook
 *
 * 在响应完成后优先请求后端建议，空结果时回退到 Q&A 提取和 mock 生成。
 */
export default function useSuggestionsPolling(options: {
  currentQARef: React.MutableRefObject<{
    request?: any;
    response?: any;
    abortController?: AbortController;
  }>;
  updateMessage: (message: any) => void;
}) {
  const { currentQARef, updateMessage } = options;

  const currentSessionId = useContextSelector(
    ChatAnywhereSessionsContext,
    (v) => v.currentSessionId,
  );

  const sessionIdRef = useRef(currentSessionId);
  const activePollResponseIdRef = useRef<string | null>(null);
  const sessionApi = useChatAnywhereOptions((v) => v.session?.api);

  useEffect(() => {
    sessionIdRef.current = currentSessionId;
  }, [currentSessionId]);

  const pollSuggestions = useCallback(async () => {
    const sessionId = sessionIdRef.current;
    if (!sessionId) {
      console.debug("[Suggestions] No session ID available");
      return;
    }

    const currentResponse = currentQARef.current.response;
    const turnId = currentResponse?.id;
    if (!turnId) {
      console.debug("[Suggestions] No response ID available");
      return;
    }

    activePollResponseIdRef.current = turnId;

    try {
      let suggestions = await fetchBackendSuggestions({ sessionId });

      if (!suggestions.length) {
        try {
          await (sessionApi as any)?.getSessionList?.();
        } catch (error) {
          console.debug("[Suggestions] getSessionList failed:", error);
        }

        const chatId =
          (sessionApi as any)?.getChatIdForSession?.(sessionId) ??
          (sessionApi as any)?.getRealIdForSession?.(sessionId) ??
          sessionId;
        const currentRequest = currentQARef.current.request;
        const userMessage = extractUserMessageText(
          currentRequest?.cards?.[0]?.data?.input?.[0] ?? {},
        ).trim();

        if (!userMessage) {
          console.debug("[Suggestions] No user message available");
          return;
        }

        const qaResponse = await fetchQAContent({ chatId, userMessage });
        let qaContent: QAContentResponse["qa_content"] = qaResponse.qa_content;

        if (!qaContent) {
          const assistantMessage = extractCopyableText(
            currentResponse?.cards?.[0]?.data ?? {},
          ).trim();

          if (!assistantMessage) {
            console.debug("[Suggestions] Missing assistant response text");
            return;
          }

          qaContent = {
            user_message: userMessage,
            assistant_response: assistantMessage,
          };
        }

        suggestions = await fetchGeneratedSuggestions({
          chatId,
          turnId,
          userMessage: qaContent.user_message,
          assistantMessage: qaContent.assistant_response,
        });
      }

      // 检查是否已被新的请求覆盖
      if (activePollResponseIdRef.current !== turnId) {
        console.debug(
          "[Suggestions] Request cancelled, responseId mismatch. Expected:",
          turnId,
          "Active:",
          activePollResponseIdRef.current,
        );
        return;
      }

      if (!suggestions.length) {
        return;
      }

      const latestResponse = currentQARef.current.response;
      if (latestResponse?.id !== turnId) {
        console.debug(
          "[Suggestions] Response ID mismatch, skipping update. Expected:",
          turnId,
          "Current:",
          latestResponse?.id,
        );
        return;
      }

      // 更新响应
      if (latestResponse?.cards?.[0]?.data) {
        const updatedCards = [
          {
            ...latestResponse.cards[0],
            data: {
              ...latestResponse.cards[0].data,
              suggestions,
            },
          },
          ...latestResponse.cards.slice(1),
        ];

        currentQARef.current.response = {
          ...latestResponse,
          cards: updatedCards,
        };

        updateMessage(currentQARef.current.response);
      }
    } catch (error) {
      console.debug("[Suggestions] Fetch failed:", error);
    }
  }, [currentQARef, updateMessage, sessionApi]);

  return { pollSuggestions };
}
