import dayjs from "dayjs";
import type {
  IAgentScopeRuntimeRequest,
  IAgentScopeRuntimeResponse,
} from "@/components/agentscope-chat/AgentScopeRuntimeWebUI/core/AgentScopeRuntime/types";
import type { IAgentScopeRuntimeWebUIMessage } from "@/components/agentscope-chat/AgentScopeRuntimeWebUI/core/types/IMessages";

export interface ChatMessageHeaderMeta {
  timestamp?: number;
}

export interface ChatRuntimeRequestCardData extends IAgentScopeRuntimeRequest {
  headerMeta?: ChatMessageHeaderMeta;
}

export interface ChatRuntimeResponseCardData
  extends IAgentScopeRuntimeResponse {
  headerMeta?: ChatMessageHeaderMeta;
}

function readMetadataOriginalId(metadata: unknown): string | null {
  if (!metadata || typeof metadata !== "object") return null;
  const record = metadata as Record<string, unknown>;
  const direct = record.original_id || record.originalId;
  if (typeof direct === "string" && direct.trim()) {
    return direct;
  }
  return readMetadataOriginalId(record.metadata);
}

function readObjectOriginalId(value: unknown): string | null {
  if (!value || typeof value !== "object") return null;
  const record = value as Record<string, unknown>;
  const direct = record.original_id || record.originalId;
  if (typeof direct === "string" && direct.trim()) {
    return direct;
  }
  return readMetadataOriginalId(record.metadata);
}

function isRuntimeGeneratedId(value: string): boolean {
  return value.startsWith("msg_") || value.startsWith("response_");
}

export function resolveFeedbackResponseId(
  response: ChatRuntimeResponseCardData,
): string | null {
  const output = Array.isArray(response.output) ? response.output : [];

  for (let index = output.length - 1; index >= 0; index -= 1) {
    const message = output[index];
    if (message?.role === "assistant") {
      const originalId = readObjectOriginalId(message);
      if (originalId) return originalId;
    }
  }

  const responseOriginalId = readObjectOriginalId(response);
  if (responseOriginalId) return responseOriginalId;

  for (let index = output.length - 1; index >= 0; index -= 1) {
    const message = output[index];
    if (
      message?.role === "assistant" &&
      message.id &&
      !isRuntimeGeneratedId(message.id)
    ) {
      return message.id;
    }
  }

  if (response.id && !isRuntimeGeneratedId(response.id)) {
    return response.id;
  }

  return resolveFeedbackTraceId(response);
}

function readMetadataTraceId(metadata: unknown): string | null {
  if (!metadata || typeof metadata !== "object") return null;
  const record = metadata as Record<string, unknown>;
  const direct = record.trace_id || record.traceId;
  if (typeof direct === "string" && direct.trim()) {
    return direct;
  }
  return readMetadataTraceId(record.metadata);
}

function readObjectTraceId(value: unknown): string | null {
  if (!value || typeof value !== "object") return null;
  const record = value as Record<string, unknown>;
  const direct = record.trace_id || record.traceId;
  if (typeof direct === "string" && direct.trim()) {
    return direct;
  }
  return readMetadataTraceId(record.metadata);
}

export function resolveFeedbackTraceId(
  response: ChatRuntimeResponseCardData,
): string | null {
  const direct = readObjectTraceId(response);
  if (direct) return direct;

  const output = Array.isArray(response.output) ? response.output : [];
  for (let index = output.length - 1; index >= 0; index -= 1) {
    const traceId = readObjectTraceId(output[index]);
    if (traceId) return traceId;
  }

  return null;
}

export interface ChatApprovalActionCardData {
  requestId: string;
  toolName: string;
  toolInput: Record<string, unknown>;
  triggerLabel: string;
  approveCommand: string;
  denyCommand: string;
  status?: "pending" | "approved" | "denied" | "timeout" | "superseded";
}

export interface ChatTaskRunGroupCardData {
  runId: string;
  runIndex: number;
  taskName?: string;
  collapsedByDefault?: boolean;
  finalMessages: IAgentScopeRuntimeWebUIMessage[];
  stepMessages: IAgentScopeRuntimeWebUIMessage[];
  headerMeta?: ChatMessageHeaderMeta;
}

type TimestampSource = {
  timestamp?: unknown;
};

function normalizeEpochMs(value: number): number {
  return value < 1_000_000_000_000 ? value * 1000 : value;
}

function toTimestamp(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return normalizeEpochMs(value);
  }

  if (typeof value !== "string") return null;

  const trimmed = value.trim();
  if (!trimmed) return null;

  const numeric = Number(trimmed);
  if (Number.isFinite(numeric)) {
    return normalizeEpochMs(numeric);
  }

  const parsed = Date.parse(trimmed);
  return Number.isNaN(parsed) ? null : parsed;
}

export function resolveMessageTimestamp(
  message: TimestampSource,
): number | undefined {
  return toTimestamp(message.timestamp) ?? undefined;
}

export function resolveGroupTimestamp(
  messages: TimestampSource[],
): number | undefined {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const resolved = resolveMessageTimestamp(messages[index]);
    if (resolved) return resolved;
  }

  return undefined;
}

export function formatMessageTime(timestamp?: number): string {
  if (timestamp === undefined) return "";
  return dayjs(timestamp).format("MM-DD HH:mm");
}
