import type { SourceSystemConfig } from "@/api/types/sourceSystemConfig";

export interface CurrentSourceConfigSwitchDefinition {
  key: string;
  path: string[];
  defaultValue: boolean;
  title: string;
  description: string;
}

export const CURRENT_SOURCE_SYSTEM_CONFIG_SWITCHES: CurrentSourceConfigSwitchDefinition[] = [
  {
    key: "feature_switches.chat_task_progress_enabled",
    path: ["feature_switches", "chat_task_progress_enabled"],
    defaultValue: true,
    title: "任务进度步骤条",
    description:
      "关闭后不再注入 task progress 提示词，也不会写入或展示步骤进度。",
  },
];

export function readRegisteredSwitchValue(
  config: SourceSystemConfig,
  definition: CurrentSourceConfigSwitchDefinition,
): boolean {
  let current: unknown = config;
  for (const key of definition.path) {
    if (!current || typeof current !== "object" || !(key in current)) {
      return definition.defaultValue;
    }
    current = (current as Record<string, unknown>)[key];
  }
  return typeof current === "boolean" ? current : definition.defaultValue;
}

export function writeRegisteredSwitchValue(
  config: SourceSystemConfig,
  definition: CurrentSourceConfigSwitchDefinition,
  value: boolean,
): SourceSystemConfig {
  const nextConfig = structuredClone(config);
  let current: Record<string, unknown> = nextConfig;
  definition.path.forEach((segment, index) => {
    const isLeaf = index === definition.path.length - 1;
    if (isLeaf) {
      current[segment] = value;
      return;
    }
    const nextValue = current[segment];
    if (!nextValue || typeof nextValue !== "object" || Array.isArray(nextValue)) {
      current[segment] = {};
    }
    current = current[segment] as Record<string, unknown>;
  });
  return nextConfig;
}
