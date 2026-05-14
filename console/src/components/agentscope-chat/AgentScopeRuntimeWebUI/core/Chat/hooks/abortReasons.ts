export type ChatStreamAbortKind = "detach" | "stop" | "timeout";

export interface ChatStreamAbortReason {
  code: "chat_stream_abort";
  kind: ChatStreamAbortKind;
  message?: string;
}

export function createChatStreamAbortReason(
  kind: ChatStreamAbortKind,
  message?: string,
): ChatStreamAbortReason {
  return {
    code: "chat_stream_abort",
    kind,
    ...(message ? { message } : {}),
  };
}

export function isChatStreamAbortReason(
  value: unknown,
  kind?: ChatStreamAbortKind,
): value is ChatStreamAbortReason {
  if (!value || typeof value !== "object") return false;

  const reason = value as Partial<ChatStreamAbortReason>;
  return (
    reason.code === "chat_stream_abort" &&
    (kind ? reason.kind === kind : Boolean(reason.kind))
  );
}

function isDomAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

export function isAbortLikeError(error: unknown): boolean {
  return isDomAbortError(error) || isChatStreamAbortReason(error);
}

export function shouldStopBackendForFetchAbort(
  error: unknown,
  signal?: AbortSignal,
): boolean {
  return (
    isChatStreamAbortReason(error, "timeout") ||
    isChatStreamAbortReason(signal?.reason, "timeout")
  );
}

export function getChatStreamAbortMessage(
  error: unknown,
  signal?: AbortSignal,
): string | undefined {
  if (isChatStreamAbortReason(error)) {
    return error.message;
  }

  if (isChatStreamAbortReason(signal?.reason)) {
    return signal.reason.message;
  }

  return undefined;
}
