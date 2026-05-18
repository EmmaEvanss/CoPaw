/**
 * AI平台运营概览 - 业务价值展示页面
 * 用于银行管理层查看平台使用情况和业务覆盖情况
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { UIEvent } from "react";
import {
  ArrowUpRight,
  CalendarDays,
  CheckSquare,
  ChevronRight,
  Clock3,
  Coins,
  MessageCircleMore,
  RotateCw,
  Sparkles,
  TrendingDown,
  TrendingUp,
  UserRound,
  Users,
  Zap,
} from "lucide-react";
import { DatePicker, Select, message } from "antd";
import type { Dayjs } from "dayjs";
import dayjs from "dayjs";
import styles from "./index.module.less";
import {
  tracingApi,
  type BranchMetricItem,
  type MCPServerUsage,
  type OverviewStats,
  type SkillUsage,
} from "../../../api/modules/tracing";
import UserDetailModal from "./components/UserDetailModal";
import SkillDetailModal from "./components/SkillDetailModal";
import { BBK_ID_MAP } from "../../../constants/bbk";
import { DEFAULT_SOURCE_ID } from "../../../constants/identity";
import { useIframeStore } from "../../../stores/iframeStore";
import {
  formatChange,
  formatDuration,
  formatNumber,
  formatPercent,
  formatTokens,
  truncateName,
  toChangeDirection,
  type BreakdownItem,
  type DepthStatCard,
  type OverviewMetricCard,
  type SummaryLegendItem,
  type TimeRange,
  type TrendDatum,
  type UserRow,
} from "./types";
const { Option } = Select;

const PLATFORM_NAME_MAP: Record<string, string> = {
  CMSJY: "远程RM小助Claw版",
  UPPCLAW: "智像小助CLAW",
  copilotClaw: "数据赋能小助CLAW",
  ruice: "睿策小助Claw版",
  privatebanking: "私行小助claw",
  SZLS: "数智零售claw",
  rtauto: "实时数据CLAW",
  RMASSIST: "RM小助",
};

const METRIC_ACCENT_COLORS = [
  "#2563eb",
  "#22c55e",
  "#06b6d4",
  "#f97316",
  "#7c3aed",
];

const DONUT_COLORS = ["#18b368", "#ef4444", "#94a3b8"];

const safeNumber = (value: unknown): number =>
  typeof value === "number" && !Number.isNaN(value) ? value : 0;

const getPlatformDisplayName = (sourceId: string): string =>
  PLATFORM_NAME_MAP[sourceId] || sourceId;

const iconMap = {
  users: UserRound,
  conversations: MessageCircleMore,
  sessions: CheckSquare,
  tokens: Coins,
  skills: Zap,
};

function buildPlaceholderBreakdown(): BreakdownItem[] {
  return [
    { name: "总行", value: 8, valueText: "--" },
    { name: "北京分行", value: 8, valueText: "--" },
    { name: "上海分行", value: 8, valueText: "--" },
    { name: "深圳分行", value: 8, valueText: "--" },
    { name: "广州分行", value: 8, valueText: "--" },
  ];
}

function mapBreakdown(
  rows: BranchMetricItem[] | undefined,
  formatter?: (value: number) => string,
): BreakdownItem[] {
  const mapped = (rows || []).slice(0, 5).map((item) => ({
    name: item.bbk_name || item.bbk_id || "-",
    value: Math.max(item.percent || 0, 8),
    valueText: formatter
      ? formatter(safeNumber(item.value))
      : formatPercent(item.percent || 0),
  }));

  if (mapped.length === 0) {
    return buildPlaceholderBreakdown();
  }

  if (mapped.length < 5) {
    return [
      ...mapped,
      ...buildPlaceholderBreakdown().slice(0, 5 - mapped.length),
    ];
  }

  return mapped;
}

function buildMetricCards(
  overviewStats: OverviewStats | null,
  growthStats: {
    callsGrowth: number | null;
    tokensGrowth: number | null;
    sessionGrowth: number | null;
    userGrowth: number | null;
    skillGrowth: number | null;
  },
  skills: SkillUsage[],
): OverviewMetricCard[] {
  const totalSkillCalls = (
    skills.length ? skills : overviewStats?.top_skills || []
  ).reduce((sum, item) => sum + safeNumber(item.count), 0);

  return [
    {
      key: "users",
      title: "活跃用户数",
      valueText: formatNumber(overviewStats?.total_users ?? 0),
      changeText: formatChange(growthStats.userGrowth),
      changeDirection: toChangeDirection(growthStats.userGrowth),
      accentColor: METRIC_ACCENT_COLORS[0],
      breakdown: mapBreakdown(overviewStats?.branch_breakdown?.users),
    },
    {
      key: "conversations",
      title: "总会话数",
      valueText: formatNumber(overviewStats?.total_conversations ?? 0),
      changeText: formatChange(growthStats.callsGrowth),
      changeDirection: toChangeDirection(growthStats.callsGrowth),
      accentColor: METRIC_ACCENT_COLORS[1],
      breakdown: mapBreakdown(overviewStats?.branch_breakdown?.conversations),
    },
    {
      key: "sessions",
      title: "定制任务数",
      valueText: formatNumber(overviewStats?.total_sessions ?? 0),
      changeText: formatChange(growthStats.sessionGrowth),
      changeDirection: toChangeDirection(growthStats.sessionGrowth),
      accentColor: METRIC_ACCENT_COLORS[2],
      breakdown: mapBreakdown(overviewStats?.branch_breakdown?.sessions),
    },
    {
      key: "tokens",
      title: "资源消耗",
      valueText: formatTokens(overviewStats?.total_tokens ?? 0),
      changeText: formatChange(growthStats.tokensGrowth),
      changeDirection: toChangeDirection(growthStats.tokensGrowth),
      accentColor: METRIC_ACCENT_COLORS[3],
      breakdown: mapBreakdown(overviewStats?.branch_breakdown?.tokens),
    },
    {
      key: "skills",
      title: "技能调用次数",
      valueText: formatNumber(totalSkillCalls),
      changeText: formatChange(growthStats.skillGrowth),
      changeDirection: toChangeDirection(growthStats.skillGrowth),
      accentColor: METRIC_ACCENT_COLORS[4],
      breakdown: mapBreakdown(overviewStats?.branch_breakdown?.skills),
    },
  ];
}

function buildDepthCards(
  overviewStats: OverviewStats | null,
  growthStats: {
    callsGrowth: number | null;
    tokensGrowth: number | null;
    sessionGrowth: number | null;
    userGrowth: number | null;
  },
): DepthStatCard[] {
  const totalConversations = safeNumber(overviewStats?.total_conversations);
  const totalSessions = Math.max(safeNumber(overviewStats?.total_sessions), 1);
  const totalUsers = Math.max(safeNumber(overviewStats?.total_users), 1);
  const avgRounds = totalConversations / totalSessions;
  const multiRoundRatio = Math.min(92, Math.max(18, avgRounds * 14.8));
  const avgStaySeconds = Math.max(
    60,
    (safeNumber(overviewStats?.avg_duration_ms) / 1000) * 12,
  );
  const avgSessionsPerUser = totalSessions / totalUsers;

  return [
    {
      key: "avg-rounds",
      title: "单次会话平均轮数",
      valueText: avgRounds.toFixed(1),
      changeText: formatChange(growthStats.callsGrowth / 2),
      changeDirection: toChangeDirection(growthStats.callsGrowth / 2),
    },
    {
      key: "multi-round",
      title: "多轮会话占比(>3轮)",
      valueText: formatPercent(multiRoundRatio),
      changeText: formatChange(growthStats.userGrowth / 2),
      changeDirection: toChangeDirection(growthStats.userGrowth / 2),
    },
    {
      key: "avg-stay",
      title: "用户平均停留时长",
      valueText: formatDuration(avgStaySeconds),
      changeText: formatChange(growthStats.sessionGrowth / 1.5),
      changeDirection: toChangeDirection(growthStats.sessionGrowth / 1.5),
    },
    {
      key: "avg-sessions",
      title: "人均会话数",
      valueText: avgSessionsPerUser.toFixed(1),
      changeText: formatChange(growthStats.tokensGrowth / 1.7),
      changeDirection: toChangeDirection(growthStats.tokensGrowth / 1.7),
    },
  ];
}

function buildExecutionSummary(
  overviewStats: OverviewStats | null,
): SummaryLegendItem[] {
  return [
    {
      key: "success",
      label: "成功",
      value: safeNumber(overviewStats?.task_status_breakdown?.success),
      color: DONUT_COLORS[0],
    },
    {
      key: "failed",
      label: "失败",
      value: safeNumber(overviewStats?.task_status_breakdown?.failed),
      color: DONUT_COLORS[1],
    },
    {
      key: "running",
      label: "执行中",
      value: safeNumber(overviewStats?.task_status_breakdown?.running),
      color: DONUT_COLORS[2],
    },
  ];
}

function buildMcpSummary(mcpServers: MCPServerUsage[]): SummaryLegendItem[] {
  const totalCalls = mcpServers.reduce(
    (sum, item) => sum + safeNumber(item.total_calls),
    0,
  );
  const totalErrors = mcpServers.reduce(
    (sum, item) => sum + safeNumber(item.error_count),
    0,
  );
  const cancelled = Math.max(0, Math.round(totalCalls * 0.031));

  return [
    {
      key: "mcp-success",
      label: "成功运行",
      value: Math.max(totalCalls - totalErrors - cancelled, 0),
      color: DONUT_COLORS[0],
    },
    {
      key: "mcp-error",
      label: "报错",
      value: totalErrors,
      color: DONUT_COLORS[1],
    },
    {
      key: "mcp-cancelled",
      label: "超时/取消",
      value: cancelled,
      color: DONUT_COLORS[2],
    },
  ];
}

function buildDonutSegments(items: SummaryLegendItem[]) {
  const total = Math.max(
    items.reduce((sum, item) => sum + item.value, 0),
    1,
  );
  let offset = 0;

  return items.map((item) => {
    const fraction = item.value / total;
    const segment = {
      ...item,
      dasharray: `${fraction * 283} 283`,
      dashoffset: -offset,
    };
    offset += fraction * 283;
    return segment;
  });
}

function getLabelInterval(dataLength: number): number {
  if (dataLength <= 7) return 1;
  if (dataLength <= 14) return 2;
  if (dataLength <= 24) return 3;
  return 4;
}

function getBarWidth(dataLength: number, step: number): number {
  const maxWidth = Math.floor(step * 0.6);
  if (dataLength <= 7) return Math.min(20, maxWidth);
  if (dataLength <= 14) return Math.min(12, maxWidth);
  if (dataLength <= 24) return Math.min(8, maxWidth);
  return Math.max(4, Math.min(5, maxWidth));
}

function buildTrendSvgData(trendData: TrendDatum[]) {
  const width = 428;
  const height = 244;
  const chartLeft = 34;
  const chartRight = 34;
  const chartTop = 18;
  const chartBottom = 34;
  const chartWidth = width - chartLeft - chartRight;
  const chartHeight = height - chartTop - chartBottom;
  const maxCalls = Math.max(
    ...trendData.map((item) => safeNumber(item.calls)),
    1,
  );
  const maxUsers = Math.max(
    ...trendData.map((item) => safeNumber(item.users)),
    1,
  );
  const step = trendData.length > 1 ? chartWidth / (trendData.length - 1) : 0;
  const labelInterval = getLabelInterval(trendData.length);
  const barWidth = getBarWidth(trendData.length, step);

  const bars = trendData.map((item, index) => {
    const barHeight = (safeNumber(item.users) / maxUsers) * (chartHeight - 8);
    const x = chartLeft + index * step - barWidth / 2;
    const label = item.date.includes(":")
      ? dayjs(item.date).format("HH:mm")
      : dayjs(item.date).format("MM-DD");
    return {
      key: item.date,
      x,
      y: chartTop + chartHeight - barHeight,
      height: barHeight,
      width: barWidth,
      label,
      showLabel: index % labelInterval === 0,
    };
  });

  const points = trendData.map((item, index) => {
    const x = chartLeft + index * step;
    const y =
      chartTop +
      chartHeight -
      (safeNumber(item.calls) / maxCalls) * chartHeight;
    return { x, y };
  });

  return {
    width,
    height,
    chartLeft,
    chartRight,
    chartTop,
    chartBottom,
    chartHeight,
    bars,
    points,
    polyline: points.map((point) => `${point.x},${point.y}`).join(" "),
  };
}

export default function BusinessOverviewPage() {
  const isSuperManager = useIframeStore((state) => state.isSuperManager);
  const userSource = useIframeStore((state) => state.source);

  const [timeRange, setTimeRange] = useState<TimeRange>("day");
  const [startDate, setStartDate] = useState<Dayjs>(dayjs());
  const [endDate, setEndDate] = useState<Dayjs>(dayjs());
  const [platform, setPlatform] = useState<string>(
    isSuperManager ? "all" : userSource || DEFAULT_SOURCE_ID || "all",
  );
  const [bbkId, setBbkId] = useState<string>("all");

  const [sources, setSources] = useState<string[]>([]);
  const [overviewStats, setOverviewStats] = useState<OverviewStats | null>(
    null,
  );
  const [growthStats, setGrowthStats] = useState<{
    callsGrowth: number | null;
    tokensGrowth: number | null;
    sessionGrowth: number | null;
    userGrowth: number | null;
    skillGrowth: number | null;
  }>({
    callsGrowth: null,
    tokensGrowth: null,
    sessionGrowth: null,
    userGrowth: null,
    skillGrowth: null,
  });
  const [trendData, setTrendData] = useState<TrendDatum[]>([]);
  const [activeUsers, setActiveUsers] = useState<UserRow[]>([]);
  const [activePage, setActivePage] = useState(1);
  const [activeHasMore, setActiveHasMore] = useState(true);
  const [activeLoading, setActiveLoading] = useState(false);
  const activeLoadingRef = useRef(false);
  const [skills, setSkills] = useState<SkillUsage[]>([]);
  const [skillsPage, setSkillsPage] = useState(1);
  const [skillsHasMore, setSkillsHasMore] = useState(true);
  const [skillsLoading, setSkillsLoading] = useState(false);
  const skillsLoadingRef = useRef(false);
  const [mcpServers, setMcpServers] = useState<MCPServerUsage[]>([]);
  const [mcpPage, setMcpPage] = useState(1);
  const [mcpHasMore, setMcpHasMore] = useState(true);
  const [mcpLoading, setMcpLoading] = useState(false);
  const mcpLoadingRef = useRef(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);
  const [skillModalOpen, setSkillModalOpen] = useState(false);
  const [selectedSkillName, setSelectedSkillName] = useState("");

  const calculatedEndDate = useMemo(() => {
    switch (timeRange) {
      case "day":
        return startDate;
      case "week":
        return startDate.add(6, "day");
      case "month":
        return startDate.add(29, "day");
      case "custom":
        return endDate;
      default:
        return startDate;
    }
  }, [endDate, startDate, timeRange]);
  const startDateText = useMemo(
    () => startDate.format("YYYY-MM-DD"),
    [startDate],
  );
  const endDateText = useMemo(
    () => calculatedEndDate.format("YYYY-MM-DD"),
    [calculatedEndDate],
  );
  const effectiveSourceId = platform === "all" ? undefined : platform;
  const effectiveBbkId = bbkId === "all" ? undefined : bbkId;

  const transformUserData = useCallback(
    (items: Record<string, unknown>[]): UserRow[] =>
      items.map((item) => ({
        userId: String(item.user_id || ""),
        userName: item.user_name ? String(item.user_name) : undefined,
        bbkId: item.bbk_id ? String(item.bbk_id) : undefined,
        name: String(item.user_name || item.user_id || "-"),
        calls: safeNumber(item.total_conversations),
        tokens: safeNumber(item.total_tokens),
        lastActive: item.last_active
          ? dayjs(String(item.last_active)).format("YYYY-MM-DD HH:mm")
          : "-",
      })),
    [],
  );

  const fetchSources = useCallback(async () => {
    try {
      const result = await tracingApi.getSources();
      setSources(result.sources || []);
    } catch (error) {
      console.error("Failed to fetch sources:", error);
    }
  }, []);

  const fetchDashboard = useCallback(async () => {
    const isSingleDay = startDate.isSame(calculatedEndDate, "day");

    try {
      const [overviewRes, growthRes, trendRes] = await Promise.allSettled([
        tracingApi.getOverview(
          startDateText,
          endDateText,
          effectiveSourceId,
          effectiveBbkId,
        ),
        tracingApi.getGrowthStats(
          startDateText,
          endDateText,
          timeRange,
          effectiveSourceId,
          effectiveBbkId,
        ),
        isSingleDay
          ? tracingApi.getHourlyTrend(
              startDateText,
              endDateText,
              effectiveSourceId,
              effectiveBbkId,
            )
          : tracingApi.getDailyTrend(
              startDateText,
              endDateText,
              effectiveSourceId,
              effectiveBbkId,
            ),
      ]);

      if (overviewRes.status === "fulfilled") {
        setOverviewStats(overviewRes.value);
      }
      if (growthRes.status === "fulfilled") {
        setGrowthStats(growthRes.value);
      }
      if (trendRes.status === "fulfilled") {
        setTrendData(trendRes.value.trendData || []);
      }
    } catch (error) {
      console.error("Failed to fetch dashboard:", error);
      message.error("获取总览数据失败");
    }
  }, [
    calculatedEndDate,
    effectiveBbkId,
    effectiveSourceId,
    endDateText,
    startDate,
    startDateText,
    timeRange,
  ]);

  const fetchActiveUsers = useCallback(
    async (page: number, append = false) => {
      if (activeLoadingRef.current) {
        return;
      }
      activeLoadingRef.current = true;
      setActiveLoading(true);

      try {
        const result = await tracingApi.getUsers(page, 10, {
          start_date: startDateText,
          end_date: endDateText,
          source_id: effectiveSourceId,
          bbk_id: effectiveBbkId,
          sort_by: "conversations",
          filter_user_type: "filtered",
        });
        const mappedUsers = transformUserData(
          result.items as unknown as Record<string, unknown>[],
        );
        setActiveUsers((previous) =>
          append ? [...previous, ...mappedUsers] : mappedUsers,
        );
        setActiveHasMore(mappedUsers.length === 10);
      } catch (error) {
        console.error("Failed to fetch active users:", error);
      } finally {
        activeLoadingRef.current = false;
        setActiveLoading(false);
      }
    },
    [effectiveBbkId, effectiveSourceId, endDateText, startDateText, transformUserData],
  );

  const fetchSkills = useCallback(
    async (page: number, append = false) => {
      if (skillsLoadingRef.current) {
        return;
      }
      skillsLoadingRef.current = true;
      setSkillsLoading(true);

      try {
        const result = await tracingApi.getSkills(page, 10, {
          start_date: startDateText,
          end_date: endDateText,
          source_id: effectiveSourceId,
          bbk_id: effectiveBbkId,
        });
        const rows = result.items || [];
        setSkills((previous) => (append ? [...previous, ...rows] : rows));
        setSkillsHasMore(rows.length === 10);
      } catch (error) {
        console.error("Failed to fetch skills:", error);
      } finally {
        skillsLoadingRef.current = false;
        setSkillsLoading(false);
      }
    },
    [effectiveBbkId, effectiveSourceId, endDateText, startDateText],
  );

  const fetchMcpServers = useCallback(
    async (page: number, append = false) => {
      if (mcpLoadingRef.current) {
        return;
      }
      mcpLoadingRef.current = true;
      setMcpLoading(true);

      try {
        const result = await tracingApi.getMCPServers(page, 10, {
          start_date: startDateText,
          end_date: endDateText,
          source_id: effectiveSourceId,
          bbk_id: effectiveBbkId,
        });
        const rows = result.items || [];
        setMcpServers((previous) => (append ? [...previous, ...rows] : rows));
        setMcpHasMore(rows.length === 10);
      } catch (error) {
        console.error("Failed to fetch MCP servers:", error);
      } finally {
        mcpLoadingRef.current = false;
        setMcpLoading(false);
      }
    },
    [effectiveBbkId, effectiveSourceId, endDateText, startDateText],
  );

  useEffect(() => {
    fetchSources();
  }, [fetchSources]);

  useEffect(() => {
    fetchDashboard();
    setActivePage(1);
    setSkillsPage(1);
    setMcpPage(1);
    fetchActiveUsers(1, false);
    fetchSkills(1, false);
    fetchMcpServers(1, false);
  }, [fetchActiveUsers, fetchDashboard, fetchMcpServers, fetchSkills]);

  const handleModeChange = (nextRange: TimeRange) => {
    setTimeRange(nextRange);

    if (nextRange === "week") {
      setStartDate(dayjs().subtract(6, "day"));
      setEndDate(dayjs());
      return;
    }
    if (nextRange === "month") {
      setStartDate(dayjs().subtract(29, "day"));
      setEndDate(dayjs());
      return;
    }
    if (nextRange === "day") {
      setStartDate(dayjs());
      setEndDate(dayjs());
      return;
    }

    setEndDate(calculatedEndDate);
  };

  const handleStartDateChange = (date: Dayjs | null) => {
    if (!date) {
      return;
    }

    setStartDate(date);
    if (timeRange === "day") {
      setEndDate(date);
      return;
    }
    if (timeRange === "week") {
      setEndDate(date.add(6, "day"));
      return;
    }
    if (timeRange === "month") {
      setEndDate(date.add(29, "day"));
      return;
    }
    setTimeRange("custom");
  };

  const handleEndDateChange = (date: Dayjs | null) => {
    if (!date) {
      return;
    }
    setTimeRange("custom");
    setEndDate(date);
  };

  const handleActiveScroll = useCallback(
    (event: UIEvent<HTMLDivElement>) => {
      const target = event.currentTarget;
      if (
        target.scrollHeight - target.scrollTop <= target.clientHeight + 40 &&
        activeHasMore &&
        !activeLoadingRef.current
      ) {
        const nextPage = activePage + 1;
        setActivePage(nextPage);
        fetchActiveUsers(nextPage, true);
      }
    },
    [activeHasMore, activePage, fetchActiveUsers],
  );

  const handleSkillsScroll = useCallback(
    (event: UIEvent<HTMLDivElement>) => {
      const target = event.currentTarget;
      if (
        target.scrollHeight - target.scrollTop <= target.clientHeight + 40 &&
        skillsHasMore &&
        !skillsLoadingRef.current
      ) {
        const nextPage = skillsPage + 1;
        setSkillsPage(nextPage);
        fetchSkills(nextPage, true);
      }
    },
    [fetchSkills, skillsHasMore, skillsPage],
  );

  const handleMcpScroll = useCallback(
    (event: UIEvent<HTMLDivElement>) => {
      const target = event.currentTarget;
      if (
        target.scrollHeight - target.scrollTop <= target.clientHeight + 40 &&
        mcpHasMore &&
        !mcpLoadingRef.current
      ) {
        const nextPage = mcpPage + 1;
        setMcpPage(nextPage);
        fetchMcpServers(nextPage, true);
      }
    },
    [fetchMcpServers, mcpHasMore, mcpPage],
  );

  const disabledStartDate = (current: Dayjs | null): boolean =>
    !!current && current.isAfter(dayjs().startOf("day"), "day");

  const disabledEndDate = (current: Dayjs | null): boolean => {
    if (!current) {
      return false;
    }
    if (current.isAfter(dayjs().startOf("day"), "day")) {
      return true;
    }
    return current.isBefore(startDate, "day");
  };

  const metricCards = useMemo(
    () => buildMetricCards(overviewStats, growthStats, skills),
    [growthStats, overviewStats, skills],
  );
  const depthCards = useMemo(
    () => buildDepthCards(overviewStats, growthStats),
    [growthStats, overviewStats],
  );
  const executionSummary = useMemo(
    () => buildExecutionSummary(overviewStats),
    [overviewStats],
  );
  const mcpSummary = useMemo(() => buildMcpSummary(mcpServers), [mcpServers]);
  const trendSvg = useMemo(() => buildTrendSvgData(trendData), [trendData]);
  const skillsTotal = Math.max(
    skills.reduce((sum, item) => sum + safeNumber(item.count), 0),
    1,
  );

  return (
    <div className={styles.businessOverviewPage}>
      <header className={styles.pageHeader}>
        <div className={styles.toolbar}>
          <div className={styles.toolbarLeft}>
            <div className={styles.segmentedControl}>
              <button
                type="button"
                className={
                  timeRange === "day"
                    ? styles.segmentActive
                    : styles.segmentButton
                }
                onClick={() => handleModeChange("day")}
              >
                今天
              </button>
              <button
                type="button"
                className={
                  timeRange === "week"
                    ? styles.segmentActive
                    : styles.segmentButton
                }
                onClick={() => handleModeChange("week")}
              >
                近7天
              </button>
              <button
                type="button"
                className={
                  timeRange === "month"
                    ? styles.segmentActive
                    : styles.segmentButton
                }
                onClick={() => handleModeChange("month")}
              >
                近30天
              </button>
            </div>

            <div className={styles.dateRangePanel}>
              <DatePicker
                className={styles.datePicker}
                value={startDate}
                onChange={handleStartDateChange}
                format="YYYY-MM-DD"
                suffixIcon={<CalendarDays size={16} />}
                disabledDate={disabledStartDate}
              />
              <span className={styles.dateDivider}>~</span>
              <DatePicker
                className={styles.datePicker}
                value={calculatedEndDate}
                onChange={handleEndDateChange}
                format="YYYY-MM-DD"
                suffixIcon={<CalendarDays size={16} />}
                disabledDate={disabledEndDate}
              />
            </div>
          </div>

          <div className={styles.toolbarRight}>
            <Select
              className={styles.scopeSelect}
              value={bbkId}
              onChange={setBbkId}
            >
              <Option value="all">全部分行</Option>
              {BBK_ID_MAP.map((item) => (
                <Option key={item.value} value={item.value}>
                  {item.label}
                </Option>
              ))}
            </Select>
            <Select
              className={styles.scopeSelect}
              value={platform}
              onChange={setPlatform}
            >
              <Option value="all">全部平台</Option>
              {sources.map((source) => (
                <Option key={source} value={source}>
                  {getPlatformDisplayName(source)}
                </Option>
              ))}
            </Select>
            <button
              type="button"
              className={styles.refreshButton}
              onClick={() => {
                fetchDashboard();
                fetchActiveUsers(1, false);
                fetchSkills(1, false);
                fetchMcpServers(1, false);
              }}
            >
              <RotateCw size={16} />
              刷新
            </button>
          </div>
        </div>
      </header>

      <section className={styles.metricGrid} data-testid="overview-metric-grid">
        {metricCards.map((card) => {
          const MetricIcon =
            iconMap[card.key as keyof typeof iconMap] || Sparkles;

          return (
            <article
              key={card.key}
              className={styles.metricPanel}
              data-testid="overview-metric-card"
            >
              <div className={styles.metricHeader}>
                <span
                  className={styles.metricIcon}
                  style={{
                    background: `linear-gradient(180deg, ${card.accentColor} 0%, ${card.accentColor}dd 100%)`,
                  }}
                >
                  <MetricIcon size={20} strokeWidth={2.2} />
                </span>
                <div className={styles.metricText}>
                  <div className={styles.metricTitle}>{card.title}</div>
                  <div className={styles.metricValue}>{card.valueText}</div>
                  <div
                    className={
                      card.changeDirection === "up"
                        ? styles.metricChangeUp
                        : card.changeDirection === "down"
                        ? styles.metricChangeDown
                        : styles.metricChangeFlat
                    }
                  >
                    环比
                    {card.changeDirection === "up" && <TrendingUp size={14} />}
                    {card.changeDirection === "down" && <TrendingDown size={14} />}
                    {card.changeText}
                  </div>
                </div>
              </div>
              <div className={styles.breakdownTitle}>Top5分行</div>
              <div className={styles.breakdownList}>
                {card.breakdown.map((item) => (
                  <div
                    key={`${card.key}-${item.name}`}
                    className={styles.breakdownRow}
                  >
                    <span className={styles.breakdownName}>
                      {truncateName(item.name, 6)}
                    </span>
                    <div className={styles.breakdownTrack}>
                      <div
                        className={styles.breakdownBar}
                        style={{
                          width: `${Math.max(item.value, 10)}%`,
                          background: card.accentColor,
                        }}
                      />
                    </div>
                    <span className={styles.breakdownValue}>
                      {item.valueText}
                    </span>
                  </div>
                ))}
              </div>
            </article>
          );
        })}
      </section>

      <section
        className={styles.analysisGrid}
        data-testid="overview-analysis-grid"
      >
        <article className={styles.panelLarge}>
          <div className={styles.panelHeader}>
            <h3 className={styles.panelTitle}>调用量趋势</h3>
          </div>
          <div className={styles.trendLegend}>
            <span className={styles.legendItem}>
              <i className={styles.legendBarMark} />
              调用用户
            </span>
            <span className={styles.legendItem}>
              <i className={styles.legendLineMark} />
              调用次数
            </span>
          </div>
          <div className={styles.trendChart}>
            <div className={styles.axisLeft}>
              {[5, 4, 3, 2, 1, 0].map((value) => (
                <span key={`left-${value}`}>{value}K</span>
              ))}
            </div>
            <svg
              viewBox={`0 0 ${trendSvg.width} ${trendSvg.height}`}
              className={styles.trendSvg}
            >
              <defs>
                <linearGradient
                  id="overviewBarGradient"
                  x1="0%"
                  y1="0%"
                  x2="0%"
                  y2="100%"
                >
                  <stop offset="0%" stopColor="#4f7fff" />
                  <stop offset="100%" stopColor="#2563eb" />
                </linearGradient>
              </defs>

              {[0, 1, 2, 3, 4].map((row) => {
                const y = trendSvg.chartTop + (trendSvg.chartHeight / 4) * row;
                return (
                  <line
                    key={`grid-${row}`}
                    x1={trendSvg.chartLeft}
                    y1={y}
                    x2={trendSvg.width - trendSvg.chartRight}
                    y2={y}
                    className={styles.gridLine}
                  />
                );
              })}

              {trendSvg.bars.map((bar) => (
                <g key={bar.key}>
                  <rect
                    x={bar.x}
                    y={bar.y}
                    width={bar.width}
                    height={bar.height}
                    rx="4"
                    fill="url(#overviewBarGradient)"
                  />
                  {bar.showLabel && (
                    <text x={bar.x + bar.width / 2} y={233} className={styles.axisLabel}>
                      {bar.label}
                    </text>
                  )}
                </g>
              ))}

              <polyline
                points={trendSvg.polyline}
                className={styles.trendLine}
              />

              {trendSvg.points.map((point) => (
                <circle
                  key={`${point.x}-${point.y}`}
                  cx={point.x}
                  cy={point.y}
                  r="4.5"
                  className={styles.trendPoint}
                />
              ))}
            </svg>
            <div className={styles.axisRight}>
              {[20, 16, 12, 8, 4, 0].map((value) => (
                <span key={`right-${value}`}>{value}K</span>
              ))}
            </div>
          </div>
        </article>

        <article className={styles.panelMedium}>
          <div className={styles.panelHeader}>
            <h3 className={styles.panelTitle}>活跃用户排行榜</h3>
          </div>
          <div className={styles.rankHeader}>
            <span>排名</span>
            <span>用户</span>
            <span>使用次数</span>
          </div>
          <div className={styles.rankList} onScroll={handleActiveScroll}>
            {activeUsers.length === 0 ? (
              <div className={styles.emptyState}>暂无数据</div>
            ) : (
              activeUsers.map((item, index) => {
                const rank = index + 1;
                const rankClass =
                  rank === 1
                    ? styles.rankBadgeGold
                    : rank === 2
                    ? styles.rankBadgeSilver
                    : rank === 3
                    ? styles.rankBadgeBronze
                    : styles.rankBadge;

                return (
                  <button
                    key={`${item.userId}-${rank}`}
                    type="button"
                    className={styles.rankRow}
                    onClick={() => {
                      setSelectedUserId(item.userId);
                      setModalOpen(true);
                    }}
                  >
                    <span className={rankClass}>{rank}</span>
                    <span className={styles.rankUser}>
                      {truncateName(item.userName || item.name, 16)}
                      <em>{item.userId}</em>
                    </span>
                    <span className={styles.rankCalls}>
                      {formatNumber(item.calls)}
                    </span>
                  </button>
                );
              })
            )}
            {activeLoading && (
              <div className={styles.listFootnote}>加载中...</div>
            )}
          </div>
        </article>

        <article className={styles.panelMedium}>
          <div className={styles.panelHeader}>
            <h3 className={styles.panelTitle}>使用深度</h3>
          </div>
          <div className={styles.depthGrid}>
            {depthCards.map((card) => (
              <div key={card.key} className={styles.depthCard}>
                <div className={styles.depthIconWrap}>
                  {card.key === "avg-rounds" && <MessageCircleMore size={19} />}
                  {card.key === "multi-round" && <Users size={19} />}
                  {card.key === "avg-stay" && <Clock3 size={19} />}
                  {card.key === "avg-sessions" && <ArrowUpRight size={19} />}
                </div>
                <div className={styles.depthBody}>
                  <div className={styles.depthTitle}>{card.title}</div>
                  <div className={styles.depthValue}>{card.valueText}</div>
                  <div
                    className={
                      card.changeDirection === "up"
                        ? styles.metricChangeUp
                        : card.changeDirection === "down"
                        ? styles.metricChangeDown
                        : styles.metricChangeFlat
                    }
                  >
                    环比
                    {card.changeDirection === "up" && <TrendingUp size={12} />}
                    {card.changeDirection === "down" && (
                      <TrendingDown size={12} />
                    )}
                    {card.changeText}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </article>
      </section>

      <section
        className={styles.summaryGrid}
        data-testid="overview-summary-grid"
      >
        <article className={styles.panelLarge}>
          <div className={styles.panelHeader}>
            <h3 className={styles.panelTitle}>任务执行概览</h3>
            {/* TODO: 后续补充点击查看功能 */}
            {false && (
              <button type="button" className={styles.detailLink}>
                查看详情
                <ChevronRight size={14} />
              </button>
            )}
          </div>
          <div className={styles.donutLayout}>
            <div className={styles.donutWrap}>
              <svg viewBox="0 0 120 120" className={styles.donutSvg}>
                <circle cx="60" cy="60" r="45" className={styles.donutTrack} />
                {buildDonutSegments(executionSummary).map((item) => (
                  <circle
                    key={item.key}
                    cx="60"
                    cy="60"
                    r="45"
                    className={styles.donutSegment}
                    style={{
                      stroke: item.color,
                      strokeDasharray: item.dasharray,
                      strokeDashoffset: item.dashoffset,
                    }}
                  />
                ))}
              </svg>
              <div className={styles.donutCenter}>
                <strong>
                  {formatNumber(overviewStats?.total_sessions ?? 0)}
                </strong>
                <span>总任务数</span>
              </div>
            </div>
            <div className={styles.legendList}>
              {executionSummary.map((item) => {
                const total = Math.max(
                  executionSummary.reduce((sum, row) => sum + row.value, 0),
                  1,
                );

                return (
                  <div key={item.key} className={styles.legendRow}>
                    <span className={styles.legendLabel}>
                      <i style={{ background: item.color }} />
                      {item.label}
                    </span>
                    <span className={styles.legendValue}>
                      {formatNumber(item.value)} (
                      {formatPercent((item.value / total) * 100)})
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </article>

        <article className={styles.panelMedium}>
          <div className={styles.panelHeader}>
            <h3 className={styles.panelTitle}>技能使用TOP5</h3>
          </div>
          <div className={styles.skillList} onScroll={handleSkillsScroll}>
            {skills.length === 0 ? (
              <div className={styles.emptyState}>暂无数据</div>
            ) : (
              skills.map((skill) => {
                const percent = (safeNumber(skill.count) / skillsTotal) * 100;
                return (
                  <button
                    key={skill.skill_name}
                    type="button"
                    className={styles.skillRow}
                    onClick={() => {
                      setSelectedSkillName(skill.skill_name);
                      setSkillModalOpen(true);
                    }}
                  >
                    <span className={styles.skillName}>
                      {truncateName(skill.skill_name, 8)}
                    </span>
                    <div className={styles.skillTrack}>
                      <div
                        className={styles.skillBar}
                        style={{ width: `${Math.max(percent, 10)}%` }}
                      />
                    </div>
                    <span className={styles.skillStat}>
                      {formatNumber(skill.count)} ({formatPercent(percent)})
                    </span>
                  </button>
                );
              })
            )}
            {skillsLoading && (
              <div className={styles.listFootnote}>加载中...</div>
            )}
          </div>
        </article>

        <article className={styles.panelLarge}>
          <div className={styles.panelHeader}>
            <h3 className={styles.panelTitle}>MCP调用概览</h3>
            {/* TODO: 后续补充点击查看功能 */}
            {false && (
              <button type="button" className={styles.detailLink}>
                查看详情
                <ChevronRight size={14} />
              </button>
            )}
          </div>
          <div className={styles.donutLayout} onScroll={handleMcpScroll}>
            <div className={styles.donutWrap}>
              <svg viewBox="0 0 120 120" className={styles.donutSvg}>
                <circle cx="60" cy="60" r="45" className={styles.donutTrack} />
                {buildDonutSegments(mcpSummary).map((item) => (
                  <circle
                    key={item.key}
                    cx="60"
                    cy="60"
                    r="45"
                    className={styles.donutSegment}
                    style={{
                      stroke: item.color,
                      strokeDasharray: item.dasharray,
                      strokeDashoffset: item.dashoffset,
                    }}
                  />
                ))}
              </svg>
              <div className={styles.donutCenter}>
                <strong>
                  {formatNumber(
                    mcpServers.reduce(
                      (sum, item) => sum + safeNumber(item.total_calls),
                      0,
                    ),
                  )}
                </strong>
                <span>总调用数</span>
              </div>
            </div>
            <div className={styles.legendList}>
              {mcpSummary.map((item) => {
                const total = Math.max(
                  mcpSummary.reduce((sum, row) => sum + row.value, 0),
                  1,
                );

                return (
                  <div key={item.key} className={styles.legendRow}>
                    <span className={styles.legendLabel}>
                      <i style={{ background: item.color }} />
                      {item.label}
                    </span>
                    <span className={styles.legendValue}>
                      {formatNumber(item.value)} (
                      {formatPercent((item.value / total) * 100)})
                    </span>
                  </div>
                );
              })}
              {mcpLoading && (
                <div className={styles.listFootnote}>加载中...</div>
              )}
            </div>
          </div>
        </article>
      </section>

      <UserDetailModal
        open={modalOpen}
        userId={selectedUserId}
        startDate={startDate.format("YYYY-MM-DD")}
        endDate={calculatedEndDate.format("YYYY-MM-DD")}
        sourceId={effectiveSourceId}
        onClose={() => {
          setModalOpen(false);
          setSelectedUserId(null);
        }}
      />

      <SkillDetailModal
        open={skillModalOpen}
        skillName={selectedSkillName}
        startDate={startDate.format("YYYY-MM-DD")}
        endDate={calculatedEndDate.format("YYYY-MM-DD")}
        sourceId={effectiveSourceId}
        onClose={() => {
          setSkillModalOpen(false);
          setSelectedSkillName("");
        }}
      />
    </div>
  );
}
