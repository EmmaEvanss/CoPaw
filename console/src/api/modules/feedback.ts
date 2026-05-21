import { request } from "../request";
import type {
  FeedbackLookupResponse,
  FeedbackSessionLookupResponse,
  FeedbackSubmitPayload,
  FeedbackSubmitResponse,
} from "../types/feedback";

export const feedbackApi = {
  getSessionFeedbacks: (params?: {
    chatId?: string | null;
    sessionId?: string | null;
  }) => {
    const search = new URLSearchParams();
    if (params?.chatId) {
      search.set("chat_id", params.chatId);
    }
    if (params?.sessionId) {
      search.set("session_id", params.sessionId);
    }
    const query = search.toString();
    return request<FeedbackSessionLookupResponse>(
      `/feedback/session${query ? `?${query}` : ""}`,
    );
  },
  getFeedback: (params: { responseId?: string | null; traceId?: string | null }) => {
    const search = new URLSearchParams();
    if (params.responseId) {
      search.set("response_id", params.responseId);
    }
    if (params.traceId) {
      search.set("trace_id", params.traceId);
    }
    const query = search.toString();
    return request<FeedbackLookupResponse>(
      `/feedback/current${query ? `?${query}` : ""}`,
    );
  },
  submitFeedback: (payload: FeedbackSubmitPayload) =>
    request<FeedbackSubmitResponse>("/feedback", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
