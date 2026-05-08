import { fetchSuggestions } from "@/api/modules/suggestions";
import { useCallback, useRef, useEffect } from "react";
import { useContextSelector } from "use-context-selector";
import { ChatAnywhereSessionsContext } from "../../Context/ChatAnywhereSessionsContext";

/**
 * 猜你想问建议获取 Hook
 *
 * 在响应完成后请求后端生成的建议，并更新到当前响应中
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
      const suggestions = await fetchSuggestions({ sessionId });

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
  }, [currentQARef, updateMessage]);

  return { pollSuggestions };
}
