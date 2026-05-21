import type { EffectiveSourceSystemConfig } from "@/api/types/sourceSystemConfig";

function readBooleanLikeValue(value: unknown): boolean | null {
  if (typeof value === "boolean") {
    return value;
  }
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    if (["true", "1", "yes", "on"].includes(normalized)) {
      return true;
    }
    if (["false", "0", "no", "off"].includes(normalized)) {
      return false;
    }
  }
  return null;
}

export function isChatTaskProgressEnabled(
  config: EffectiveSourceSystemConfig | null,
): boolean {
  const rawValue = config?.config?.feature_switches;
  if (!rawValue || typeof rawValue !== "object") {
    return true;
  }
  const enabled = (rawValue as Record<string, unknown>)
    .chat_task_progress_enabled;
  return readBooleanLikeValue(enabled) ?? true;
}
