/**
 * AI平台运营概览 - 业务价值展示页面
 * 用于银行管理层查看平台使用情况和业务覆盖情况
 */

import { useState, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { Row, Col, Tooltip, Select, DatePicker, message } from "antd";
import {
  Users,
  Building2,
  Puzzle,
  Zap,
  Clock,
  TrendingUp,
  TrendingDown,
} from "lucide-react";
import dayjs from "dayjs";
import styles from "./index.module.less";
import { tracingApi } from "../../../api/modules/tracing";
import {
  formatNumber,
  formatTokens,
  formatChange,
  formatDuration,
  truncateName,
  type UserRow,
  type SkillRow,
  type TimeRange,
  type PlatformType,
} from "./types";

const { Option } = Select;

// 颜色配置
const CHART_COLORS = [
  "#1890ff",
  "#52c41a",
  "#faad14",
  "#f5222d",
  "#722ed1",
  "#13c2c2",
  "#eb2f96",
  "#a0d911",
];

// 柱状图颜色
const BAR_COLORS = [
  "linear-gradient(90deg, #1890ff 0%, #69c0ff 100%)",
  "linear-gradient(90deg, #52c41a 0%, #95de64 100%)",
  "linear-gradient(90deg, #faad14 0%, #ffe58f 100%)",
  "linear-gradient(90deg, #f5222d 0%, #ff7875 100%)",
  "linear-gradient(90deg, #722ed1 0%, #b37feb 100%)",
];

export default function BusinessOverviewPage() {
  const { t } = useTranslation();
  const [timeRange, setTimeRange] = useState<TimeRange>("day");
  const [startDate, setStartDate] = useState<dayjs.Dayjs>(dayjs());
  const [endDate, setEndDate] = useState<dayjs.Dayjs>(dayjs());
  const [platform, setPlatform] = useState<string>("all");

  // 平台列表（从API获取）
  const [sources, setSources] = useState<string[]>([]);

  // 数据状态
  const [loading, setLoading] = useState(false);
  const [overviewStats, setOverviewStats] = useState<any>(null);
  const [growthStats, setGrowthStats] = useState({
    callsGrowth: 0,
    tokensGrowth: 0,
    sessionGrowth: 0,
    userGrowth: 0,
    platformGrowth: 0,
  });
  const [channelDistribution, setChannelDistribution] = useState<{
    platformUserDistribution: { name: string; value: number }[];
    platformCallDistribution: { name: string; value: number }[];
    totalPlatforms: number;
  }>({
    platformUserDistribution: [],
    platformCallDistribution: [],
    totalPlatforms: 0,
  });
  const [trendData, setTrendData] = useState<{
    date: string;
    calls: number;
    tokens: number;
    users: number;
  }[]>([]);
  const [topUsers, setTopUsers] = useState<UserRow[]>([]);

  // 计算结束日期
  const calculateEndDate = (start: dayjs.Dayjs, mode: TimeRange): dayjs.Dayjs => {
    switch (mode) {
      case "day":
        return start;
      case "week":
        return start.add(6, "day");
      case "month":
        return start.add(1, "month").subtract(1, "day");
      case "custom":
        return endDate;
      default:
        return start;
    }
  };

  // 获取平台列表
  const fetchSources = useCallback(async () => {
    try {
      const res = await tracingApi.getSources();
      setSources(res.sources || []);
    } catch (error) {
      console.error("Failed to fetch sources:", error);
    }
  }, []);

  // 初始加载平台列表
  useEffect(() => {
    fetchSources();
  }, [fetchSources]);

  // 获取数据
  const fetchData = useCallback(async () => {
    setLoading(true);
    const startStr = startDate.format("YYYY-MM-DD");
    const endStr = endDate.format("YYYY-MM-DD");
    // 用于筛选的 source_id（"all" 表示不筛选，其他值表示筛选特定平台）
    const filterSourceId = platform === "all" ? undefined : platform;

    // 趋势图始终使用近30天数据（不受顶部日期选择器影响）
    const trendEndDate = dayjs();
    const trendStartDate = trendEndDate.subtract(29, "day");
    const trendStartStr = trendStartDate.format("YYYY-MM-DD");
    const trendEndStr = trendEndDate.format("YYYY-MM-DD");

    try {
      // 并行请求所有数据
      // 核心运营指标、趋势、模型分布、用户分析等需要根据平台筛选
      // 平台用户分布和平台调用次数分布不筛选（显示所有平台）
      // 趋势图始终使用近30天数据
      const [overviewRes, growthRes, channelRes, trendRes, usersRes] = await Promise.allSettled([
        tracingApi.getOverview(startStr, endStr, filterSourceId),
        tracingApi.getGrowthStats(startStr, endStr, timeRange, filterSourceId),
        tracingApi.getChannelDistribution("all", startStr, endStr), // 始终显示所有平台的分布
        tracingApi.getDailyTrend(trendStartStr, trendEndStr, filterSourceId), // 始终近30天
        tracingApi.getUsers(1, 5, { start_date: startStr, end_date: endStr, source_id: filterSourceId }),
      ]);

      // 处理 overview stats
      if (overviewRes.status === "fulfilled") {
        setOverviewStats(overviewRes.value);
      }

      // 处理 growth stats
      if (growthRes.status === "fulfilled") {
        setGrowthStats(growthRes.value);
      }

      // 处理 channel distribution
      if (channelRes.status === "fulfilled") {
        setChannelDistribution(channelRes.value);
      }

      // 处理 trend data
      if (trendRes.status === "fulfilled") {
        setTrendData(trendRes.value.trendData || []);
      }

      // 处理 top users
      if (usersRes.status === "fulfilled") {
        const users = usersRes.value.items.map((u: any) => ({
          userId: u.user_id,
          name: u.user_id, // 后端没返回name，用user_id代替
          calls: u.total_conversations,
          tokens: u.total_tokens,
          lastActive: u.last_active
            ? dayjs(u.last_active).format("YYYY-MM-DD HH:mm")
            : "-",
        }));
        setTopUsers(users);
      }
    } catch (error) {
      console.error("Failed to fetch data:", error);
      message.error("获取数据失败");
    } finally {
      setLoading(false);
    }
  }, [startDate, endDate, timeRange, platform]);

  // 初始加载和日期变化时获取数据
  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // 处理开始日期变化
  const handleStartDateChange = (date: dayjs.Dayjs | null) => {
    if (date) {
      setStartDate(date);
      if (timeRange === "day") {
        setEndDate(date);
      } else if (timeRange === "week") {
        setEndDate(date.add(6, "day"));
      } else if (timeRange === "month") {
        setEndDate(date.add(1, "month").subtract(1, "day"));
      }
    }
  };

  // 禁用不符合时间范围要求的日期
  const disabledDate = (current: dayjs.Dayjs | null): boolean => {
    if (!current) return false;
    const today = dayjs().startOf("day");
    // 禁用未来日期
    if (current.isAfter(today, "day")) {
      return true;
    }
    // 周模式：起始日期不能太早（确保有完整的7天范围在今天之前）
    if (timeRange === "week") {
      const minStart = today.subtract(6, "day");
      return current.isBefore(minStart, "day");
    }
    // 月模式：起始日期不能太早（确保有完整的30天范围在今天之前）
    if (timeRange === "month") {
      const minStart = today.subtract(29, "day");
      return current.isBefore(minStart, "day");
    }
    return false;
  };

  // 处理模式切换
  const handleModeChange = (mode: TimeRange) => {
    setTimeRange(mode);
    const today = dayjs().startOf("day");
    if (mode === "day") {
      // 日模式：显示今天
      setStartDate(today);
      setEndDate(today);
    } else if (mode === "week") {
      // 周模式：显示最近7天（今天往前推6天 + 今天）
      const weekStart = today.subtract(6, "day");
      setStartDate(weekStart);
      setEndDate(today);
    } else if (mode === "month") {
      // 月模式：显示最近30天（今天往前推29天 + 今天）
      const monthStart = today.subtract(29, "day");
      setStartDate(monthStart);
      setEndDate(today);
    }
    // custom 模式不自动调整日期，用户手动选择
  };

  // 处理结束日期变化
  const handleEndDateChange = (date: dayjs.Dayjs | null) => {
    if (date) {
      setEndDate(date);
    }
  };

  const calculatedEndDate = calculateEndDate(startDate, timeRange);

  // 趋势标题固定为近30天（趋势图始终显示近30天数据，不受顶部日期选择器影响）
  const getTrendTitle = () => {
    return "近30天使用趋势";
  };

  // 计算指标数据
  const metricData = {
    totalCalls: overviewStats?.total_conversations || 0,
    callsGrowth: growthStats.callsGrowth,
    totalTokens: overviewStats?.total_tokens || 0,
    tokensGrowth: growthStats.tokensGrowth,
    avgResponseTime: 0,
    responseTimeGrowth: 0,
    avgDuration: overviewStats?.avg_duration_ms
      ? (overviewStats.avg_duration_ms / 1000)
      : 0,
    sessionCount: overviewStats?.total_sessions || 0,
    sessionGrowth: growthStats.sessionGrowth,
  };

  // 平台使用情况数据
  const platformData = {
    totalUsers: overviewStats?.total_users || 0,
    userGrowth: growthStats.userGrowth,
    totalPlatforms: channelDistribution.totalPlatforms,
    platformGrowth: growthStats.platformGrowth,
    platformUserDistribution: channelDistribution.platformUserDistribution,
    platformCallDistribution: channelDistribution.platformCallDistribution,
  };

  // ============================================================
  // 渲染：统计卡片
  // ============================================================
  const renderStatCard = (
    label: string,
    value: number,
    change: number,
    icon: React.ReactNode,
    color: string,
  ) => (
    <Col xs={24} sm={12} lg={6}>
      <div className={styles.statCard}>
        <div className={styles.statLabel}>
          <span
            className={styles.icon}
            style={{ background: `${color}15`, color }}
          >
            {icon}
          </span>
          <span>{label}</span>
        </div>
        <div className={styles.statValue}>{formatNumber(value)}</div>
        <div
          className={`${styles.statChange} ${
            change > 0
              ? styles.positive
              : change < 0
              ? styles.negative
              : styles.neutral
          }`}
        >
          {change > 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
          <span>{formatChange(change)}</span>
          <span style={{ marginLeft: 4, color: "#999", fontWeight: 400 }}>
            环比
          </span>
        </div>
      </div>
    </Col>
  );

  // ============================================================
  // 渲染：饼图（使用 SVG 实现简单饼图）
  // ============================================================
  const renderPieChart = (
    chartData: { name: string; value: number }[],
  ) => {
    const total = chartData.reduce((sum, item) => sum + item.value, 0);
    const radius = 70;
    const cx = 100;
    const cy = 100;

    let currentAngle = -90;
    const paths = chartData.map((item, index) => {
      const percentage = item.value / total;
      const angle = percentage * 360;
      const startAngle = currentAngle;
      const endAngle = currentAngle + angle;
      currentAngle = endAngle;

      const startRad = (startAngle * Math.PI) / 180;
      const endRad = (endAngle * Math.PI) / 180;

      const x1 = cx + radius * Math.cos(startRad);
      const y1 = cy + radius * Math.sin(startRad);
      const x2 = cx + radius * Math.cos(endRad);
      const y2 = cy + radius * Math.sin(endRad);

      const largeArc = angle > 180 ? 1 : 0;

      const d = `M ${cx} ${cy} L ${x1} ${y1} A ${radius} ${radius} 0 ${largeArc} 1 ${x2} ${y2} Z`;

      return (
        <path
          key={index}
          d={d}
          fill={CHART_COLORS[index % CHART_COLORS.length]}
          stroke="#fff"
          strokeWidth="2"
        >
          <title>
            {item.name}: {item.value} ({(percentage * 100).toFixed(1)}%)
          </title>
        </path>
      );
    });

    return (
      <div className={styles.pieChartContainer}>
        <svg width="200" height="200" viewBox="0 0 200 200">
          {paths}
        </svg>
      </div>
    );
  };

  // ============================================================
  // 渲染：图例
  // ============================================================
  const renderLegend = (chartData: { name: string; value: number }[]) => {
    const total = chartData.reduce((sum, item) => sum + item.value, 0);
    return (
      <div className={styles.pieLegend}>
        {chartData.map((item, index) => (
          <Tooltip
            key={index}
            title={`${item.value} (${((item.value / total) * 100).toFixed(
              1,
            )}%)`}
          >
            <span className={styles.legendItem}>
              <span
                className={styles.legendDot}
                style={{
                  background: CHART_COLORS[index % CHART_COLORS.length],
                }}
              />
              <span>{item.name}</span>
            </span>
          </Tooltip>
        ))}
      </div>
    );
  };

  // ============================================================
  // 渲染：折线图（使用 SVG 实现简单折线图）
  // ============================================================
  const renderLineChart = (
    chartData: { date: string; calls: number; tokens: number; users: number }[],
    height: number = 280,
  ) => {
    if (!chartData || chartData.length === 0) return null;
    if (chartData.length === 1) {
      // 单条数据时显示简单提示
      const d = chartData[0];
      return (
        <div className={styles.trendChartContainer}>
          <div style={{ textAlign: "center", padding: "100px 0", color: "#999" }}>
            <div>日期: {d.date}</div>
            <div>调用次数: {formatNumber(d.calls)}</div>
            <div>Token消耗: {formatTokens(d.tokens)}</div>
            <div>用户数: {formatNumber(d.users)}</div>
          </div>
        </div>
      );
    }

    const padding = { top: 20, right: 20, bottom: 40, left: 60 };
    const width = 800;
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;

    const maxCalls = Math.max(...chartData.map((d) => d.calls), 1);
    const maxTokens = Math.max(...chartData.map((d) => d.tokens), 1);
    const maxUsers = Math.max(...chartData.map((d) => d.users), 1);

    const xScale = (index: number) =>
      (index / (chartData.length - 1)) * chartWidth + padding.left;
    const yCallsScale = (value: number) =>
      chartHeight - (value / maxCalls) * chartHeight + padding.top;
    const yTokensScale = (value: number) =>
      chartHeight - (value / maxTokens) * chartHeight + padding.top;
    const yUsersScale = (value: number) =>
      chartHeight - (value / maxUsers) * chartHeight + padding.top;

    // 生成折线路径
    const callsPath = chartData
      .map(
        (d, i) => `${i === 0 ? "M" : "L"} ${xScale(i)} ${yCallsScale(d.calls)}`,
      )
      .join(" ");
    const tokensPath = chartData
      .map(
        (d, i) =>
          `${i === 0 ? "M" : "L"} ${xScale(i)} ${yTokensScale(d.tokens)}`,
      )
      .join(" ");
    const usersPath = chartData
      .map(
        (d, i) => `${i === 0 ? "M" : "L"} ${xScale(i)} ${yUsersScale(d.users)}`,
      )
      .join(" ");

    // Y轴刻度
    const yTicks = [0, 0.25, 0.5, 0.75, 1].map((ratio) => ({
      y: chartHeight * ratio + padding.top,
      label: formatNumber(maxCalls * (1 - ratio)),
    }));

    // X轴刻度（显示部分日期）
    const xTicks = [
      0,
      Math.floor(chartData.length / 2),
      chartData.length - 1,
    ].map((i) => ({
      x: xScale(i),
      label: chartData[i].date.slice(5),
    }));

    return (
      <div className={styles.trendChartContainer}>
        <svg
          width="100%"
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          preserveAspectRatio="xMidYMid meet"
        >
          {/* Y轴 */}
          {yTicks.map((tick, i) => (
            <g key={`y-${i}`}>
              <line
                x1={padding.left}
                y1={tick.y}
                x2={width - padding.right}
                y2={tick.y}
                stroke="#f0f0f0"
                strokeDasharray="4,4"
              />
              <text
                x={padding.left - 8}
                y={tick.y + 4}
                textAnchor="end"
                fontSize="11"
                fill="#999"
              >
                {tick.label}
              </text>
            </g>
          ))}

          {/* X轴 */}
          {xTicks.map((tick, i) => (
            <text
              key={`x-${i}`}
              x={tick.x}
              y={height - 8}
              textAnchor="middle"
              fontSize="11"
              fill="#999"
            >
              {tick.label}
            </text>
          ))}

          {/* 调用次数折线 */}
          <path
            d={callsPath}
            fill="none"
            stroke="#1890ff"
            strokeWidth="2.5"
            strokeLinecap="round"
          />

          {/* Token折线 */}
          <path
            d={tokensPath}
            fill="none"
            stroke="#52c41a"
            strokeWidth="2"
            strokeLinecap="round"
            strokeDasharray="6,3"
          />

          {/* 用户折线 */}
          <path
            d={usersPath}
            fill="none"
            stroke="#faad14"
            strokeWidth="2"
            strokeLinecap="round"
          />

          {/* 数据点 */}
          {chartData
            .filter(
              (_, i) =>
                i === 0 ||
                i === chartData.length - 1 ||
                i === Math.floor(chartData.length / 2),
            )
            .map((d) => (
              <circle
                key={d.date}
                cx={xScale(chartData.indexOf(d))}
                cy={yCallsScale(d.calls)}
                r="4"
                fill="#1890ff"
              />
            ))}
        </svg>
      </div>
    );
  };

  // ============================================================
  // 渲染：柱状图
  // ============================================================
  const renderBarChart = (
    chartData: { name: string; value: number }[],
    height: number = 220,
  ) => {
    const maxValue = Math.max(...chartData.map((d) => d.value));

    return (
      <div className={styles.barChartContainer} style={{ height }}>
        {chartData.map((item, index) => {
          const percentage = (item.value / maxValue) * 100;
          return (
            <div key={index} className={styles.barItem}>
              <span className={styles.barLabel}>{item.name}</span>
              <div className={styles.barTrack}>
                <div
                  className={styles.barFill}
                  style={{
                    width: `${percentage}%`,
                    background: BAR_COLORS[index % BAR_COLORS.length],
                  }}
                />
                <span className={styles.barValue}>
                  {formatTokens(item.value)}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  // ============================================================
  // 渲染：技能列表
  // ============================================================
  const renderSkillList = (skills: SkillRow[], metric: "calls" | "tokens") => (
    <div className={styles.skillList}>
      {skills.map((skill, index) => (
        <div key={skill.name} className={styles.skillItem}>
          <span
            className={`${styles.rank} ${
              index === 0
                ? styles.top1
                : index === 1
                ? styles.top2
                : index === 2
                ? styles.top3
                : styles.normal
            }`}
          >
            {index + 1}
          </span>
          <span className={styles.skillName}>{skill.name}</span>
          <span className={styles.skillValue}>
            {metric === "calls"
              ? formatNumber(skill.calls)
              : formatTokens(skill.tokens)}
          </span>
        </div>
      ))}
    </div>
  );

  // ============================================================
  // 渲染：用户列表
  // ============================================================
  const renderUserList = (users: UserRow[], metric: "calls" | "lastActive") => (
    <div className={styles.userList}>
      <div className={styles.userHeader}>
        <span className={styles.userHeaderRank}>#</span>
        <span className={styles.userHeaderName}>姓名</span>
        <span className={styles.userHeaderValue}>
          {metric === "calls" ? "调用次数" : "最后活跃"}
        </span>
      </div>
      {users.map((user, index) => (
        <div key={user.userId} className={styles.userItem}>
          <span
            className={`${styles.rank} ${
              index === 0
                ? styles.top1
                : index === 1
                ? styles.top2
                : index === 2
                ? styles.top3
                : styles.normal
            }`}
          >
            {index + 1}
          </span>
          <span className={styles.userName}>
            {user.name}
            <span className={styles.userId}>({user.userId})</span>
          </span>
          <span className={styles.userValue}>
            {metric === "calls"
              ? formatNumber(user.calls)
              : user.lastActive}
          </span>
        </div>
      ))}
    </div>
  );

  // ============================================================
  // 主渲染
  // ============================================================
  return (
    <div className={styles.businessOverviewPage}>
      {/* 页面筛选工具栏 */}
      <div className={styles.header}>
        <div className={styles.filterGroup}>
          <div className={styles.segmentedControl}>
            <span
              className={`${styles.segmentItem} ${timeRange === "day" ? styles.active : ""}`}
              onClick={() => handleModeChange("day")}
            >
              日
            </span>
            <span
              className={`${styles.segmentItem} ${timeRange === "week" ? styles.active : ""}`}
              onClick={() => handleModeChange("week")}
            >
              周
            </span>
            <span
              className={`${styles.segmentItem} ${timeRange === "month" ? styles.active : ""}`}
              onClick={() => handleModeChange("month")}
            >
              月
            </span>
            <span
              className={`${styles.segmentItem} ${timeRange === "custom" ? styles.active : ""}`}
              onClick={() => handleModeChange("custom")}
            >
              自定义
            </span>
          </div>
          <div className={styles.dateRangeDisplay}>
            <DatePicker
              className={styles.datePicker}
              value={startDate}
              onChange={handleStartDateChange}
              format="YYYY-MM-DD"
              disabledDate={disabledDate}
            />
            <span className={styles.dateRangeArrow}>→</span>
            <DatePicker
              className={styles.datePicker}
              value={calculatedEndDate}
              onChange={handleEndDateChange}
              disabled={timeRange !== "custom"}
              format="YYYY-MM-DD"
            />
          </div>
        </div>
        <Select
          className={styles.platformSelect}
          placeholder="选择平台"
          style={{ width: 180 }}
          value={platform}
          onChange={(v) => setPlatform(v)}
        >
          <Option value="all">全部平台</Option>
          {sources.map((source) => (
            <Option key={source} value={source}>
              {source}
            </Option>
          ))}
        </Select>
      </div>

      {/* ==================== 第一屏：核心运营指标 + 趋势分析 ==================== */}
      <div className={styles.sectionTitle}>
        <span>📈 核心运营指标</span>
      </div>
      <div className={styles.metricsRow}>
        <div className={styles.metricCard}>
          <div className={styles.metricLabel}>总调用次数</div>
          <div className={styles.metricValue}>
            {formatNumber(metricData.totalCalls)}
          </div>
          <div
            className={`${styles.metricChange} ${
              metricData.callsGrowth > 0 ? styles.positive : styles.negative
            }`}
          >
            {formatChange(metricData.callsGrowth)} 环比
          </div>
        </div>
        <div className={styles.metricCard}>
          <div className={styles.metricLabel}>总Token消耗</div>
          <div className={styles.metricValue}>
            {formatTokens(metricData.totalTokens)}
          </div>
          <div
            className={`${styles.metricChange} ${
              metricData.tokensGrowth > 0 ? styles.positive : styles.negative
            }`}
          >
            {formatChange(metricData.tokensGrowth)} 环比
          </div>
        </div>
        <div className={styles.metricCard}>
          <div className={styles.metricLabel}>总使用用户</div>
          <div className={styles.metricValue}>
            {formatNumber(platformData.totalUsers)}
          </div>
          <div
            className={`${styles.metricChange} ${
              platformData.userGrowth > 0 ? styles.positive : styles.negative
            }`}
          >
            {formatChange(platformData.userGrowth)} 环比
          </div>
        </div>
        <div className={styles.metricCard}>
          <div className={styles.metricLabel}>接入平台数</div>
          <div className={styles.metricValue}>
            {formatNumber(platformData.totalPlatforms)}
          </div>
          <div
            className={`${styles.metricChange} ${
              platformData.platformGrowth > 0 ? styles.positive : styles.negative
            }`}
          >
            {formatChange(platformData.platformGrowth)} 环比
          </div>
        </div>
      </div>

      <div className={styles.trendCard}>
        <div className={styles.trendHeader}>
          <h3 className={styles.trendTitle}>{getTrendTitle()}</h3>
          <div className={styles.trendLegend}>
            <span className={styles.legendItem}>
              <span
                className={styles.legendLine}
                style={{ background: "#1890ff" }}
              />
              调用次数
            </span>
            <span className={styles.legendItem}>
              <span
                className={styles.legendLine}
                style={{ background: "#52c41a" }}
              />
              Token消耗
            </span>
            <span className={styles.legendItem}>
              <span
                className={styles.legendLine}
                style={{ background: "#faad14" }}
              />
              用户数
            </span>
          </div>
        </div>
        {renderLineChart(trendData)}
      </div>

      {/* 热门技能和工具 */}
      <Row gutter={[16, 16]} className={styles.skillRow}>
        <Col xs={24} lg={12}>
          <div className={styles.skillCard}>
            <div className={styles.cardTitle}>🔥 热门技能 Top5</div>
            {renderBarChart(
              (overviewStats?.top_skills || []).slice(0, 5).map((s: any) => ({ name: truncateName(s.skill_name, 18), value: s.count })),
            )}
          </div>
        </Col>
        <Col xs={24} lg={12}>
          <div className={styles.skillCard}>
            <div className={styles.cardTitle}>🛠️ 热门工具 Top5</div>
            {renderBarChart(
              (overviewStats?.top_mcp_tools || []).slice(0, 5).map((t: any) => ({ name: truncateName(t.tool_name, 18), value: t.count })),
            )}
          </div>
        </Col>
      </Row>

      {/* ==================== 模型使用分布 ==================== */}
      <Row gutter={[16, 16]} className={styles.modelRow}>
        <Col xs={24} lg={12}>
          <div className={styles.distributionCard}>
            <div className={styles.cardTitle}>🤖 模型使用分布</div>
            {renderPieChart(
              (overviewStats?.model_distribution || []).map((m: any) => ({ name: truncateName(m.model_name, 18), value: m.count })),
            )}
            {renderLegend(
              (overviewStats?.model_distribution || []).map((m: any) => ({ name: truncateName(m.model_name, 15), value: m.count })),
            )}
          </div>
        </Col>
        <Col xs={24} lg={12}>
          <div className={styles.distributionCard}>
            <div className={styles.cardTitle}>📊 各模型Token消耗</div>
            {renderBarChart(
              (overviewStats?.model_distribution || [])
                .sort((a: any, b: any) => b.total_tokens - a.total_tokens)
                .slice(0, 5)
                .map((m: any) => ({ name: truncateName(m.model_name, 18), value: m.total_tokens })),
              260,
            )}
          </div>
        </Col>
      </Row>

      {/* ==================== 第二屏：用户分析 ==================== */}
      <div className={styles.sectionTitle}>
        <span>👥 用户分析</span>
      </div>

      {/* 核心指标卡片 */}
      <Row gutter={[16, 16]} className={styles.statCardRow}>
        <Col xs={24} sm={12} lg={12}>
          <div className={styles.statCard}>
            <div className={styles.statLabel}>
              <span className={styles.icon} style={{ background: "#1890ff15", color: "#1890ff" }}>
                <Users size={18} />
              </span>
              <span>总会话数</span>
            </div>
            <div className={styles.statValue}>{formatNumber(metricData.sessionCount)}</div>
            <div
              className={`${styles.statChange} ${
                metricData.sessionGrowth > 0 ? styles.positive : styles.negative
              }`}
            >
              {metricData.sessionGrowth > 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
              <span>{formatChange(metricData.sessionGrowth)}</span>
              <span style={{ marginLeft: 4, color: "#999", fontWeight: 400 }}>环比</span>
            </div>
          </div>
        </Col>
        <Col xs={24} sm={12} lg={12}>
          <div className={styles.statCard}>
            <div className={styles.statLabel}>
              <span className={styles.icon} style={{ background: "#52c41a15", color: "#52c41a" }}>
                <Clock size={18} />
              </span>
              <span>平均会话时长</span>
            </div>
            <div className={styles.statValue}>
              {Number(metricData.avgDuration).toFixed(1)}
              <span className={styles.suffix}>s</span>
            </div>
          </div>
        </Col>
      </Row>

      {/* 分布图 + 用户排行榜 */}
      <Row gutter={[16, 16]} className={styles.distributionRow}>
        <Col xs={24} lg={12}>
          <div className={styles.distributionCard}>
            <div className={styles.cardTitle}>📱 平台用户分布</div>
            {renderPieChart(platformData.platformUserDistribution)}
            {renderLegend(platformData.platformUserDistribution)}
          </div>
        </Col>
        <Col xs={24} lg={12}>
          <div className={styles.distributionCard}>
            <div className={styles.cardTitle}>📞 平台调用次数分布</div>
            {renderPieChart(platformData.platformCallDistribution)}
            {renderLegend(platformData.platformCallDistribution)}
          </div>
        </Col>
      </Row>

      {/* 用户排行榜 */}
      <Row gutter={[16, 16]} className={styles.userRow}>
        <Col xs={24} lg={12}>
          <div className={styles.userCard}>
            <div className={styles.cardTitle}>🏆 调用数 Top5</div>
            {renderUserList(
              [...topUsers].sort((a, b) => b.calls - a.calls).slice(0, 5),
              "calls",
            )}
          </div>
        </Col>
        <Col xs={24} lg={12}>
          <div className={styles.userCard}>
            <div className={styles.cardTitle}>🕐 最近活跃 Top5</div>
            {renderUserList(
              [...topUsers]
                .sort((a, b) => new Date(b.lastActive).getTime() - new Date(a.lastActive).getTime())
                .slice(0, 5),
              "lastActive",
            )}
          </div>
        </Col>
      </Row>
    </div>
  );
}
