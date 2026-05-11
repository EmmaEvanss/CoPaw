import { fetchPostTurnValidation } from "@/api/modules/postTurnValidation";
import { useCallback, useEffect, useRef } from "react";
import { useContextSelector } from "use-context-selector";
import { ChatAnywhereSessionsContext } from "../../Context/ChatAnywhereSessionsContext";

export default function usePostTurnValidationPolling(options: {
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

  const fetchPendingValidation = useCallback(async (): Promise<boolean> => {
    const sessionId = sessionIdRef.current;
    if (!sessionId) {
      return false;
    }

    const currentResponse = currentQARef.current.response;
    const turnId = currentResponse?.id;
    if (!turnId) {
      return false;
    }

    activePollResponseIdRef.current = turnId;

    const result = await fetchPostTurnValidation({ sessionId });
    if (!result || result.status !== "needs_confirmation") {
      return false;
    }

    if (activePollResponseIdRef.current !== turnId) {
      return true;
    }

    const latestResponse = currentQARef.current.response;
    if (latestResponse?.id !== turnId || !latestResponse?.cards?.[0]?.data) {
      return true;
    }

    const updatedCards = [
      {
        ...latestResponse.cards[0],
        data: {
          ...latestResponse.cards[0].data,
          post_turn_validation: {
            id: result.id,
            status: result.status,
            reason: result.reason,
            expires_at: result.expires_at,
          },
        },
      },
      ...latestResponse.cards.slice(1),
    ];

    currentQARef.current.response = {
      ...latestResponse,
      cards: updatedCards,
    };
    updateMessage(currentQARef.current.response);
    return true;
  }, [currentQARef, updateMessage]);

  return { fetchPendingValidation };
}
