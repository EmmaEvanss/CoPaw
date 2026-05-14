import type { ChatSpec } from "@/api/types/chat";
import type { IAgentScopeRuntimeWebUISession } from "@/components/agentscope-chat";
import { getResolvedChatId } from "../../sessionApi/resolvedSessionMapping";

export type HistorySession = IAgentScopeRuntimeWebUISession & {
  createdAt?: string | null;
  meta?: Record<string, unknown>;
  realId?: string;
};

export function getHistorySessionTargetId(session: HistorySession): string {
  return session.realId || session.id || "";
}

export function isHistorySessionActive(
  session: HistorySession | undefined,
  currentChatId: string | null | undefined,
): boolean {
  if (!session || !currentChatId) {
    return false;
  }

  // 检查直接匹配
  if (session.id === currentChatId || session.realId === currentChatId) {
    return true;
  }

  // 检查映射匹配：currentChatId 可能是真实UUID，而 session.id 是临时时间戳
  const resolvedId = getResolvedChatId(currentChatId);
  if (resolvedId && session.id === resolvedId) {
    return true;
  }

  // 反向检查：session.id 可能是临时时间戳，映射到 currentChatId
  const resolvedFromSession = getResolvedChatId(session.id);
  if (resolvedFromSession && resolvedFromSession === currentChatId) {
    return true;
  }

  return false;
}

export function buildHistorySessions(chats: ChatSpec[]): HistorySession[] {
  return [...chats]
    .reverse()
    .filter((chat) => chat.meta?.session_kind !== "task")
    .map((chat) => ({
      id: chat.id,
      name: chat.name || "新会话",
      messages: [],
      meta: chat.meta,
      createdAt: chat.created_at,
    }));
}
