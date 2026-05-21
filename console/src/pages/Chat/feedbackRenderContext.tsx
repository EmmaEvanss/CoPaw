import { createContext, useContext } from "react";
import type { ReactNode } from "react";
import type { FeedbackRecord } from "@/api/types/feedback";
import type { ResponseFeedbackTaskMeta } from "./components/ResponseFeedbackCard";
import type { ChatRuntimeResponseCardData } from "./messageMeta";
import type { FeedbackLookupMap } from "./feedbackLookup";

export interface ChatFeedbackRenderContextValue {
  feedbackChatId: string | null;
  feedbackLookup?: FeedbackLookupMap;
  feedbackLookupPending: boolean;
  feedbackSessionId: string | null;
  feedbackTask: ResponseFeedbackTaskMeta | null;
  onFeedbackSaved?: (
    feedback: FeedbackRecord,
    response: ChatRuntimeResponseCardData,
  ) => void;
}

const DEFAULT_VALUE: ChatFeedbackRenderContextValue = {
  feedbackChatId: null,
  feedbackLookup: undefined,
  feedbackLookupPending: false,
  feedbackSessionId: null,
  feedbackTask: null,
};

const ChatFeedbackRenderContext =
  createContext<ChatFeedbackRenderContextValue>(DEFAULT_VALUE);

export function ChatFeedbackRenderProvider(props: {
  children: ReactNode;
  value: ChatFeedbackRenderContextValue;
}) {
  return (
    <ChatFeedbackRenderContext.Provider value={props.value}>
      {props.children}
    </ChatFeedbackRenderContext.Provider>
  );
}

export function useChatFeedbackRenderContext() {
  return useContext(ChatFeedbackRenderContext);
}
