import { Descriptions, Tag, Tooltip } from "antd";
import { useTranslation } from "react-i18next";
import { UserStats, SessionStats, ModelUsage, ToolUsage, SkillUsage, MCPToolUsage } from "../../../../../api/modules/tracing";
import { useMemo } from "react";

interface UserStatsHeaderProps {
  userStats: UserStats;
  sessionStats?: SessionStats | null;
}

/** 获取使用统计数据的活跃来源（用于模型、工具、技能） */
function getActiveUsageStats(
  sessionStats: SessionStats | null | undefined,
  userStats: UserStats
): { model_usage: ModelUsage[]; mcp_tools_used: MCPToolUsage[]; skills_used: SkillUsage[] } {
  // 如果选中了会话，使用会话级数据；否则使用用户级数据
  const active = sessionStats || userStats;
  return {
    model_usage: active.model_usage || [],
    mcp_tools_used: active.mcp_tools_used || [],
    skills_used: active.skills_used || [],
  };
}

/** 计算内容是否超过指定行数 */
function useTruncatedTags(
  items: Array<{ name: string; count: number; error_count?: number }>,
  containerWidth: number = 700,
  lineHeight: number = 2
): {
  displayItems: Array<{ name: string; count: number; error_count?: number }>;
  hasMore: boolean;
  hiddenCount: number;
} {
  return useMemo(() => {
    if (items.length === 0) {
      return { displayItems: [], hasMore: false, hiddenCount: 0 };
    }

    // 估算每个tag的宽度
    // 中文字符约 14px，英文/数字约 8px，取平均 10px
    const avgCharWidth = 10;
    // Tag 的 padding + margin + border 等额外空间
    const extraPadding = 28;

    let currentLineWidth = 0;
    let lineCount = 1;
    let displayCount = 0;

    for (const item of items) {
      const tagText = `${item.name}: ${item.count} calls`;
      const estimatedWidth = tagText.length * avgCharWidth + extraPadding;

      if (currentLineWidth + estimatedWidth > containerWidth) {
        lineCount++;
        currentLineWidth = estimatedWidth;
      } else {
        currentLineWidth += estimatedWidth;
      }

      if (lineCount <= lineHeight) {
        displayCount++;
      } else {
        break;
      }
    }

    const displayItems = items.slice(0, displayCount);
    const hasMore = items.length > displayCount;
    const hiddenCount = items.length - displayCount;

    return { displayItems, hasMore, hiddenCount };
  }, [items, containerWidth, lineHeight]);
}

/** 格式化 token 数量 */
function formatTokens(tokens: number): string {
  if (!tokens) return "0";
  if (tokens < 1000) return tokens.toString();
  if (tokens < 1000000) return `${(tokens / 1000).toFixed(1)}K`;
  return `${(tokens / 1000000).toFixed(2)}M`;
}

/** 格式化时长 */
function formatDuration(ms: number): string {
  if (!ms) return "-";
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}m`;
}

/** 标签列表组件，支持截断和tooltip */
function TagList({
  items,
  colorFn,
  getTooltipContent,
}: {
  items: Array<{ name: string; count: number; error_count?: number }>;
  colorFn?: (item: { error_count?: number }) => string;
  getTooltipContent?: (item: { name: string; count: number; error_count?: number }) => string;
}) {
  const { displayItems, hasMore, hiddenCount } = useTruncatedTags(items);

  if (items.length === 0) return null;

  // 构建完整内容的tooltip
  const fullContent = items
    .map((item) => (getTooltipContent ? getTooltipContent(item) : `${item.name}: ${item.count} calls`))
    .join(", ");

  return (
    <Tooltip title={fullContent} placement="topLeft">
      <div
        style={{
          marginTop: 8,
          maxHeight: 56,
          overflow: "hidden",
          position: "relative",
        }}
      >
        {displayItems.map((item) => (
          <Tag
            key={item.name}
            color={colorFn ? colorFn(item) : "default"}
            style={{ marginBottom: 4, marginRight: 4 }}
          >
            {item.name}: {item.count} calls
          </Tag>
        ))}
        {hasMore && (
          <Tag style={{ marginBottom: 4 }} color="processing">
            +{hiddenCount} more
          </Tag>
        )}
      </div>
    </Tooltip>
  );
}

export default function UserStatsHeader({
  userStats,
  sessionStats,
}: UserStatsHeaderProps) {
  const { t } = useTranslation();

  // 是否选中会话（用于切换模型、工具、技能的显示数据）
  const isSessionSelected = sessionStats !== null && sessionStats !== undefined;

  // 获取模型、工具、技能的活跃数据源（根据是否选中会话决定）
  const activeUsageStats = getActiveUsageStats(sessionStats, userStats);

  // 准备模型使用数据
  const modelItems = useMemo(
    () =>
      activeUsageStats.model_usage.map((m) => ({
        name: m.model_name,
        count: m.count,
      })),
    [activeUsageStats.model_usage]
  );

  // 准备 MCP 工具使用数据
  const mcpToolItems = useMemo(
    () =>
      (activeUsageStats.mcp_tools_used || []).map((tool) => ({
        name: `${tool.tool_name} (${tool.mcp_server})`,
        count: tool.count,
        error_count: tool.error_count,
      })),
    [activeUsageStats.mcp_tools_used]
  );

  // 准备技能使用数据
  const skillItems = useMemo(
    () =>
      activeUsageStats.skills_used.map((s) => ({
        name: s.skill_name,
        count: s.count,
      })),
    [activeUsageStats.skills_used]
  );

  return (
    <div>
      {/* 表格始终显示用户级别数据 */}
      <Descriptions column={2} bordered size="small">
        <Descriptions.Item label={t("analytics.totalSessions", "总会话数")} span={1}>
          {userStats.total_sessions}
        </Descriptions.Item>
        <Descriptions.Item label={t("analytics.conversations", "对话数")} span={1}>
          {userStats.total_conversations}
        </Descriptions.Item>
        <Descriptions.Item label={t("analytics.totalTokens", "总 Token")} span={1}>
          {formatTokens(userStats.total_tokens)}
        </Descriptions.Item>
        <Descriptions.Item label={t("analytics.avgDuration", "平均时长")} span={1}>
          {formatDuration(userStats.avg_duration_ms)}
        </Descriptions.Item>
        <Descriptions.Item label={t("analytics.inputTokens", "输入 Token")} span={1}>
          {formatTokens(userStats.input_tokens)}
        </Descriptions.Item>
        <Descriptions.Item label={t("analytics.outputTokens", "输出 Token")} span={1}>
          {formatTokens(userStats.output_tokens)}
        </Descriptions.Item>
      </Descriptions>

      {/* 模型使用 - 根据会话选中状态切换数据来源 */}
      {modelItems.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <span style={{ fontWeight: 500, marginRight: 8 }}>
            模型使用{isSessionSelected ? "（当前会话）" : ""}:
          </span>
          <TagList items={modelItems} />
        </div>
      )}

      {/* MCP 工具使用 - 根据会话选中状态切换数据来源 */}
      {mcpToolItems.length > 0 && (
        <div style={{ marginTop: 8 }}>
          <span style={{ fontWeight: 500, marginRight: 8 }}>
            工具使用{isSessionSelected ? "（当前会话）" : ""}:
          </span>
          <TagList
            items={mcpToolItems}
            colorFn={(item) => (item.error_count && item.error_count > 0 ? "error" : "default")}
          />
        </div>
      )}

      {/* 技能使用 - 根据会话选中状态切换数据来源 */}
      {skillItems.length > 0 && (
        <div style={{ marginTop: 8 }}>
          <span style={{ fontWeight: 500, marginRight: 8 }}>
            技能使用{isSessionSelected ? "（当前会话）" : ""}:
          </span>
          <TagList items={skillItems} colorFn={() => "blue"} />
        </div>
      )}
    </div>
  );
}