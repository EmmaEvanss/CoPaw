import { useEffect, useMemo, useRef, useState } from "react";
import { Empty, Pagination, Spin, Tag } from "antd";
import {
  AgentScopeRuntimeWebUIComposedProvider,
  Bubble,
  IAgentScopeRuntimeWebUIMessage,
  IAgentScopeRuntimeWebUIOptions,
} from "@/components/agentscope-chat";
import { chatApi } from "../../../../../api/modules/chat";
import { tracingApi, TraceDetail, TraceListItem } from "../../../../../api/modules/tracing";
import type { ChatSpec, Message } from "../../../../../api/types";
import {
  convertMessages,
} from "../../../../Chat/sessionApi";
import RuntimeRequestCard from "../../../../Chat/components/RuntimeRequestCard";
import RuntimeResponseCard from "../../../../Chat/components/RuntimeResponseCard";
import type {
  ChatRuntimeRequestCardData,
  ChatRuntimeResponseCardData,
} from "../../../../Chat/messageMeta";
import styles from "./index.module.less";

const READONLY_OPTIONS: IAgentScopeRuntimeWebUIOptions = {
  theme: {
    locale: "zh-CN",
    bubbleList: {
      pagination: false,
    },
  },
  session: {
    multiple: false,
    api: {
      getSessionList: async () => [],
      getSession: async () => ({ id: "", name: "", messages: [] }),
      createSession: async () => [],
      updateSession: async () => [],
      removeSession: async () => [],
    },
  },
  actions: {
    list: [],
    replace: false,
  },
  api: {
    replaceMediaURL: (url: string) => url,
  },
} as unknown as IAgentScopeRuntimeWebUIOptions;

const READONLY_CARDS = {
  AgentScopeRuntimeRequestCard: (props: {
    data: ChatRuntimeRequestCardData;
  }) => <RuntimeRequestCard {...props} />,
  AgentScopeRuntimeResponseCard: (props: {
    data: ChatRuntimeResponseCardData;
    isLast?: boolean;
  }) => <RuntimeResponseCard {...props} />,
};

interface ReadOnlySessionChatProps {
  selectedSessionId: string | null;
  userId: string | null;
  traces: TraceListItem[];
  total: number;
  page: number;
  pageSize: number;
  tracesLoading: boolean;
  onPageChange: (page: number) => void;
  mockMessages?: Message[];
  mockSource?: "chat" | "tracing";
}

function findChatBySessionId(
  chats: ChatSpec[],
  sessionId: string,
): ChatSpec | undefined {
  return chats.find(
    (chat) => chat.id === sessionId || chat.session_id === sessionId,
  );
}

function buildTextContent(text: string) {
  return [{ type: "text", text, status: "completed" }];
}

function detailsToMessages(details: TraceDetail[]): Message[] {
  return [...details]
    .sort((a, b) => {
      return (
        new Date(a.trace.start_time).getTime() -
        new Date(b.trace.start_time).getTime()
      );
    })
    .flatMap((detail) => {
      const messages: Message[] = [];
      if (detail.trace.user_message) {
        messages.push({
          id: `${detail.trace.trace_id}-user`,
          role: "user",
          object: "message",
          type: "message",
          content: buildTextContent(detail.trace.user_message),
          timestamp: detail.trace.start_time,
        });
      }
      if (detail.trace.model_output) {
        messages.push({
          id: `${detail.trace.trace_id}-assistant`,
          role: "assistant",
          object: "message",
          type: "message",
          content: buildTextContent(detail.trace.model_output),
          timestamp: detail.trace.end_time || detail.trace.start_time,
        });
      }
      if (!detail.trace.model_output && detail.trace.error) {
        messages.push({
          id: `${detail.trace.trace_id}-error`,
          role: "assistant",
          object: "message",
          type: "error",
          message: detail.trace.error,
          content: [],
          timestamp: detail.trace.end_time || detail.trace.start_time,
        });
      }
      return messages;
    });
}

export default function ReadOnlySessionChat({
  selectedSessionId,
  userId,
  traces,
  total,
  page,
  pageSize,
  tracesLoading,
  onPageChange,
  mockMessages,
  mockSource = "chat",
}: ReadOnlySessionChatProps) {
  const requestSeqRef = useRef(0);
  const [chatMessages, setChatMessages] = useState<
    IAgentScopeRuntimeWebUIMessage[]
  >([]);
  const [traceMessages, setTraceMessages] = useState<
    IAgentScopeRuntimeWebUIMessage[]
  >([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [traceDetailLoading, setTraceDetailLoading] = useState(false);
  const [source, setSource] = useState<"chat" | "tracing" | null>(null);

  const displayMessages = chatMessages.length > 0 ? chatMessages : traceMessages;
  const loading =
    chatLoading ||
    (!chatMessages.length && (tracesLoading || traceDetailLoading));

  useEffect(() => {
    const seq = requestSeqRef.current + 1;
    requestSeqRef.current = seq;
    setChatMessages([]);
    setTraceMessages([]);
    setSource(null);

    if (!selectedSessionId) {
      setChatLoading(false);
      return;
    }

    if (mockMessages) {
      setChatMessages(convertMessages(mockMessages));
      setSource(mockSource);
      setChatLoading(false);
      setTraceDetailLoading(false);
      return;
    }

    setChatLoading(true);
    const loadChatHistory = async () => {
      try {
        const chats = await chatApi.listChats(userId ? { user_id: userId } : undefined);
        const matchedChat = findChatBySessionId(chats, selectedSessionId);
        const chatId = matchedChat?.id || selectedSessionId;
        const history = await chatApi.getChat(chatId);
        if (requestSeqRef.current !== seq) return;

        const messages = convertMessages(history.messages || []);
        setChatMessages(messages);
        if (messages.length > 0) {
          setSource("chat");
        }
      } catch (error) {
        if (requestSeqRef.current === seq) {
          setSource("tracing");
        }
      } finally {
        if (requestSeqRef.current === seq) {
          setChatLoading(false);
        }
      }
    };

    void loadChatHistory();
  }, [selectedSessionId, userId, mockMessages, mockSource]);

  useEffect(() => {
    if (mockMessages) {
      return;
    }

    const seq = requestSeqRef.current;
    setTraceMessages([]);

    if (!selectedSessionId || chatMessages.length > 0 || traces.length === 0) {
      setTraceDetailLoading(false);
      return;
    }

    setTraceDetailLoading(true);
    const loadTraceDetails = async () => {
      try {
        const details = await Promise.all(
          [...traces]
            .reverse()
            .map((trace) => tracingApi.getTraceDetail(trace.trace_id)),
        );
        if (requestSeqRef.current !== seq) return;

        const messages = convertMessages(detailsToMessages(details));
        setTraceMessages(messages);
        if (messages.length > 0) {
          setSource("tracing");
        }
      } catch (error) {
        console.error("Failed to load trace chat details:", error);
      } finally {
        if (requestSeqRef.current === seq) {
          setTraceDetailLoading(false);
        }
      }
    };

    void loadTraceDetails();
  }, [selectedSessionId, chatMessages.length, traces, mockMessages]);

  const titleTag = useMemo(() => {
    if (!selectedSessionId) return null;
    if (source === null) {
      return <Tag>加载中</Tag>;
    }
    return (
      <Tag color={source === "chat" ? "blue" : "default"}>
        {source === "chat" ? "聊天历史" : "追踪摘要"}
      </Tag>
    );
  }, [selectedSessionId, source]);

  if (!selectedSessionId) {
    return (
      <div className={styles.readonlyChat}>
        {/* <div className={styles.readonlyChatTitle}>聊天记录</div> */}
        <div className={styles.readonlyChatEmpty}>
          <Empty description="请选择左侧会话卡片查看聊天内容" />
        </div>
      </div>
    );
  }

  return (
    <div className={styles.readonlyChat}>
      <div className={styles.readonlyChatTitleRow}>
        <div className={styles.readonlyChatTitle}>聊天记录</div>
        {/* {titleTag}
        <Tag color="green">只读</Tag> */}
      </div>

      {loading ? (
        <div className={styles.readonlyChatLoading}>
          <Spin />
        </div>
      ) : displayMessages.length === 0 ? (
        <div className={styles.readonlyChatEmpty}>
          <Empty description="暂无聊天内容" />
        </div>
      ) : (
        <AgentScopeRuntimeWebUIComposedProvider
          options={READONLY_OPTIONS}
          cards={READONLY_CARDS}
        >
          <div className={styles.readonlyChatBubbleList}>
            <Bubble.List
              pagination={false}
              order="asc"
              items={displayMessages}
              classNames={{
                wrapper: styles.readonlyBubbleWrapper,
                list: styles.readonlyBubbleList,
              }}
            />
          </div>
        </AgentScopeRuntimeWebUIComposedProvider>
      )}

      {source !== "chat" && total > pageSize && (
        <div className={styles.tracesPagination}>
          <Pagination
            simple
            current={page}
            pageSize={pageSize}
            total={total}
            onChange={onPageChange}
          />
        </div>
      )}
    </div>
  );
}
