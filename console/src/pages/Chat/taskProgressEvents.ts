import { emit } from "@/components/agentscope-chat/AgentScopeRuntimeWebUI/core/Context/useChatAnywhereEventEmitter";

export type ChatTaskProgressItem = {
  id: string;
  label: string;
  status: "todo" | "running" | "done";
};

export type ChatTaskProgressData = {
  turn_id: string;
  phase_status: "active" | "completed" | "cancelled";
  version: number;
  current_step_index: number | null;
  total_steps: number;
  title?: string;
  items: ChatTaskProgressItem[];
};

export const CHAT_TASK_PROGRESS_UPDATE_EVENT = "chat-task-progress-update";

function isTaskProgressItem(value: unknown): value is ChatTaskProgressItem {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return (
    typeof item.id === "string"
    && typeof item.label === "string"
    && (item.status === "todo"
      || item.status === "running"
      || item.status === "done")
  );
}

export function extractTaskProgress(
  value: unknown,
): ChatTaskProgressData | null | undefined {
  if (!value || typeof value !== "object") return undefined;
  const raw = value as Record<string, unknown>;
  if (!Object.prototype.hasOwnProperty.call(raw, "task_progress")) {
    return undefined;
  }

  const progress = raw.task_progress;
  if (!progress || typeof progress !== "object") {
    return null;
  }

  const payload = progress as Record<string, unknown>;
  if (
    typeof payload.turn_id !== "string"
    || (payload.phase_status !== "active"
      && payload.phase_status !== "completed"
      && payload.phase_status !== "cancelled")
    || typeof payload.version !== "number"
    || typeof payload.total_steps !== "number"
    || !Array.isArray(payload.items)
    || !payload.items.every(isTaskProgressItem)
  ) {
    return null;
  }

  const currentStepIndex =
    typeof payload.current_step_index === "number"
      ? payload.current_step_index
      : null;

  return {
    turn_id: payload.turn_id,
    phase_status: payload.phase_status,
    version: payload.version,
    current_step_index: currentStepIndex,
    total_steps: payload.total_steps,
    title: typeof payload.title === "string" ? payload.title : undefined,
    items: payload.items,
  };
}

export function emitTaskProgressUpdate(
  payload: ChatTaskProgressData | null,
): void {
  emit({
    type: CHAT_TASK_PROGRESS_UPDATE_EVENT,
    data: payload,
  });
}
