import {
  AlertTriangle,
  Banknote,
  CalendarDays,
  CheckCircle2,
  Eye,
  Landmark,
  RefreshCw,
  UserRoundCheck,
  type LucideIcon,
} from "lucide-react";
import { DatePicker, Select, Tooltip } from "antd";
import dayjs, { type Dayjs } from "dayjs";
import { useEffect, useState, type CSSProperties } from "react";
import { useSearchParams } from "react-router-dom";
import {
  monitorApi,
  type CronJobOverviewFailureReason,
  type CronJobOverviewDateFilters,
  type CronJobOverviewPageData,
} from "../../../api/modules/monitor";
import { BBK_ID_MAP, BBK_ID_TO_NAME_MAP } from "../../../constants/bbk";
import styles from "./index.module.less";

const { Option } = Select;

type TimeRange = "day" | "week" | "month" | "custom";
type SummaryMetricTone = "blue" | "green" | "orange" | "red";

type SummaryMetricDefinition = {
  key: string;
  title: string;
  unit?: string;
  footerLabel?: string;
  tone: SummaryMetricTone;
  icon: LucideIcon;
};

type SummaryMetricView = SummaryMetricDefinition & {
  value: string;
  footerValue?: string;
};

const summaryMetricDefinitions: SummaryMetricDefinition[] = [
  {
    key: "branches",
    title: "覆盖分行数",
    unit: "家",
    tone: "blue",
    icon: Landmark,
  },
  {
    key: "managers",
    title: "覆盖客户经理数",
    unit: "人",
    tone: "blue",
    icon: UserRoundCheck,
  },
  {
    key: "tasks",
    title: "定时任务数",
    unit: "个",
    footerLabel: "任务执行次数",
    tone: "blue",
    icon: CalendarDays,
  },
  {
    key: "success",
    title: "执行成功率",
    unit: "%",
    footerLabel: "成功执行数",
    tone: "green",
    icon: CheckCircle2,
  },
  {
    key: "read",
    title: "已读率",
    unit: "%",
    footerLabel: "已读任务数",
    tone: "orange",
    icon: Eye,
  },
  {
    key: "alert",
    title: "报错率",
    unit: "%",
    footerLabel: "报错执行次数",
    tone: "red",
    icon: AlertTriangle,
  },
];

const emptyOverviewData: CronJobOverviewPageData = {
  summaryMetrics: [],
  branchBehaviorRows: [],
  failureReasons: [],
  anomalySummary: {
    affectedBranches: "-",
    affectedBranchesUnit: "家",
    affectedManagers: "-",
    affectedManagersUnit: "人",
  },
  anomalyRankRows: [],
};

function isValidDateParam(value: string | null) {
  if (!value) {
    return false;
  }
  const parsed = dayjs(value);
  return parsed.isValid() && parsed.format("YYYY-MM-DD") === value;
}

function getInitialDateRange(searchParams: URLSearchParams): [Dayjs, Dayjs] {
  const startDate = searchParams.get("start_date");
  const endDate = searchParams.get("end_date");

  if (isValidDateParam(startDate) && isValidDateParam(endDate)) {
    return [dayjs(startDate), dayjs(endDate)];
  }

  return [dayjs(), dayjs()];
}

function getTimeRangeForDateRange([start, end]: [Dayjs, Dayjs]): TimeRange {
  const today = dayjs();

  if (start.isSame(today, "day") && end.isSame(today, "day")) {
    return "day";
  }
  if (
    start.isSame(today.subtract(6, "day"), "day") &&
    end.isSame(today, "day")
  ) {
    return "week";
  }
  if (
    start.isSame(today.subtract(29, "day"), "day") &&
    end.isSame(today, "day")
  ) {
    return "month";
  }
  return "custom";
}

function getInitialBbkIds(searchParams: URLSearchParams) {
  const bbkIds = searchParams.get("bbk_ids");
  return bbkIds ? bbkIds.split(",").map((item) => item.trim()).filter(Boolean) : [];
}

function SummaryCard({ metric }: { metric: SummaryMetricView }) {
  const Icon = metric.icon;

  return (
    <article className={`${styles.summaryCard} ${styles[metric.tone]}`}>
      <div className={styles.summaryMain}>
        <span className={styles.summaryIcon}>
          <Icon size={28} />
        </span>
        <div className={styles.summaryText}>
          <span className={styles.summaryTitle}>{metric.title}</span>
          <strong>
            {metric.value}
            {metric.unit ? <em>{metric.unit}</em> : null}
          </strong>
        </div>
      </div>
      {metric.footerLabel && metric.footerValue ? (
        <div className={styles.summaryFooter}>
          <span>{metric.footerLabel}</span>
          <strong>{metric.footerValue}</strong>
        </div>
      ) : null}
    </article>
  );
}

function BehaviorTable({ data }: { data: CronJobOverviewPageData["branchBehaviorRows"] }) {
  return (
    <section className={`${styles.panel} ${styles.behaviorPanel}`}>
      <h2>分行层行为分析</h2>
      <div className={styles.tableScroller}>
        <table className={styles.behaviorTable}>
          <thead>
            <tr>
              <th rowSpan={2} className={styles.indexCell} />
              <th rowSpan={2}>分行名称</th>
              <th colSpan={2} className={styles.groupRead}>
                已读（第一层）
              </th>
              <th colSpan={2} className={styles.groupDirect}>
                查看方案（并列动作）
              </th>
              <th colSpan={2} className={styles.groupBrowse}>
                点击去洞察（并列动作）
              </th>
              <th colSpan={2} className={styles.groupPhone}>
                点击去电访（并列动作）
              </th>
            </tr>
            <tr>
              <th>已读任务数</th>
              <th>已读率</th>
              <th>查看方案任务数</th>
              <th>方案点击率</th>
              <th>点击去洞察任务数</th>
              <th>洞察点击率</th>
              <th>点击去电访任务数</th>
              <th>电访点击率</th>
            </tr>
          </thead>
          <tbody>
            {data.map((row, index) => (
              <tr key={`${row.branchName}-${index}`} className={row.rank === "..." ? styles.mutedRow : undefined}>
                <td className={styles.indexCell}>{row.rank}</td>
                <td className={styles.branchName}>{row.branchName}</td>
                <td>{row.readTasks}</td>
                <td>{row.readRate}</td>
                <td>{row.directTasks}</td>
                <td>{row.directClickRate}</td>
                <td>{row.browseTasks}</td>
                <td>{row.browseClickRate}</td>
                <td>{row.phoneTasks}</td>
                <td>{row.phoneClickRate}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function DonutChart({ items }: { items: CronJobOverviewFailureReason[] }) {
  const total = items.reduce((sum, item) => sum + item.count, 0);
  const radius = 44;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;

  return (
    <div className={styles.donutWrap}>
      <svg className={styles.donutChart} viewBox="0 0 116 116" role="img" aria-label="报错原因分布">
        <circle cx="58" cy="58" r={radius} fill="none" stroke="#edf3fb" strokeWidth="16" />
        {items.map((item) => {
          const dash = total > 0 ? (item.count / total) * circumference : 0;
          const segmentStyle = {
            "--dash": dash,
            "--gap": circumference - dash,
            "--offset": -offset,
            "--segment-color": item.color,
          } as CSSProperties;
          offset += dash;

          return (
            <circle
              key={item.name}
              className={styles.donutSegment}
              cx="58"
              cy="58"
              r={radius}
              fill="none"
              strokeWidth="16"
              style={segmentStyle}
            />
          );
        })}
      </svg>
      <div className={styles.donutCenter}>
        <strong>{total.toLocaleString("en-US")}</strong>
        <span>报错执行次数</span>
      </div>
    </div>
  );
}

function FailureReasonPanel({ data }: { data: CronJobOverviewFailureReason[] }) {
  return (
    <article className={styles.reasonPanel}>
      <h3>报错原因分布（按报错执行次数）</h3>
      <div className={styles.reasonContent}>
        <DonutChart items={data} />
        <div className={styles.reasonLegend}>
          {data.map((item) => (
            <div key={item.name} className={styles.reasonRow}>
              <span>
                <i style={{ backgroundColor: item.color }} />
                {item.name}
              </span>
              <strong>
                {item.percent.toFixed(2)}% ({item.count})
              </strong>
            </div>
          ))}
        </div>
      </div>
    </article>
  );
}

function MiniSummaryCard({
  icon,
  title,
  value,
  unit,
}: {
  icon: LucideIcon;
  title: string;
  value: string;
  unit: string;
}) {
  const Icon = icon;

  return (
    <article className={styles.miniSummaryCard}>
      <span className={styles.miniIcon}>
        <Icon size={26} />
      </span>
      <div>
        <span>{title}</span>
        <strong>
          {value}
          <em>{unit}</em>
        </strong>
      </div>
    </article>
  );
}

function RankTable({ data }: { data: CronJobOverviewPageData["anomalyRankRows"] }) {
  return (
    <section className={`${styles.panel} ${styles.rankPanel}`}>
      <h2>分行异常排行</h2>
      <div className={styles.tableScroller}>
        <table className={styles.rankTable}>
          <thead>
            <tr>
              <th className={styles.indexCell} />
              <th>分行名称</th>
              <th>报错执行次数</th>
              <th>报错率</th>
              <th>受影响客户经理数</th>
            </tr>
          </thead>
          <tbody>
            {data.map((row) => (
              <tr key={row.rank}>
                <td className={styles.indexCell}>{row.rank}</td>
                <td className={styles.branchName}>{row.branchName}</td>
                <td>{row.alertExecutions}</td>
                <td>{row.alertRate}</td>
                <td>{row.affectedManagers}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default function CronJobOverviewPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialDateRange = getInitialDateRange(searchParams);
  const [overviewData, setOverviewData] = useState<CronJobOverviewPageData>(emptyOverviewData);
  const [loading, setLoading] = useState(false);
  const [timeRange, setTimeRange] = useState<TimeRange>(
    getTimeRangeForDateRange(initialDateRange),
  );
  const [dateRange, setDateRange] = useState<[Dayjs, Dayjs]>(initialDateRange);
  const [bbkIds, setBbkIds] = useState<string[]>(() => getInitialBbkIds(searchParams));

  const getOverviewFilters = (): CronJobOverviewDateFilters => ({
    start_date: dateRange[0].format("YYYY-MM-DD"),
    end_date: dateRange[1].format("YYYY-MM-DD"),
    bbk_ids: bbkIds.length > 0 ? bbkIds.join(",") : undefined,
  });

  useEffect(() => {
    let ignore = false;

    async function loadOverview() {
      setLoading(true);
      try {
        const response = await monitorApi.getCronJobOverviewPageData(getOverviewFilters());
        if (!ignore) {
          setOverviewData(response);
        }
      } catch (error) {
        console.warn("Failed to fetch cron job overview page data.", error);
      } finally {
        if (!ignore) {
          setLoading(false);
        }
      }
    }

    loadOverview();

    return () => {
      ignore = true;
    };
  }, [dateRange, bbkIds]);

  useEffect(() => {
    const nextParams = new URLSearchParams();
    nextParams.set("start_date", dateRange[0].format("YYYY-MM-DD"));
    nextParams.set("end_date", dateRange[1].format("YYYY-MM-DD"));
    if (bbkIds.length > 0) {
      nextParams.set("bbk_ids", bbkIds.join(","));
    }
    setSearchParams(nextParams, { replace: true });
  }, [dateRange, bbkIds, setSearchParams]);

  const fetchOverview = async () => {
    setLoading(true);
    try {
      const response = await monitorApi.getCronJobOverviewPageData(getOverviewFilters());
      setOverviewData(response);
    } catch (error) {
      console.warn("Failed to fetch cron job overview page data.", error);
    } finally {
      setLoading(false);
    }
  };

  const handleModeChange = (nextRange: TimeRange) => {
    setTimeRange(nextRange);
    const today = dayjs();

    if (nextRange === "day") {
      setDateRange([today, today]);
    } else if (nextRange === "week") {
      setDateRange([today.subtract(6, "day"), today]);
    } else if (nextRange === "month") {
      setDateRange([today.subtract(29, "day"), today]);
    }
  };

  const handleDateRangeChange = (dates: null | [Dayjs | null, Dayjs | null]) => {
    if (!dates?.[0] || !dates?.[1]) {
      return;
    }

    const [start, end] = dates;
    const today = dayjs();

    if (start.isSame(today, "day") && end.isSame(today, "day")) {
      setTimeRange("day");
    } else if (
      start.isSame(today.subtract(6, "day"), "day") &&
      end.isSame(today, "day")
    ) {
      setTimeRange("week");
    } else if (
      start.isSame(today.subtract(29, "day"), "day") &&
      end.isSame(today, "day")
    ) {
      setTimeRange("month");
    } else {
      setTimeRange("custom");
    }

    setDateRange([start, end]);
  };

  const disabledDate = (current: Dayjs | null): boolean =>
    !!current && current.isAfter(dayjs().startOf("day"), "day");

  const summaryMetricValues = new Map(
    overviewData.summaryMetrics.map((metric) => [metric.key, metric]),
  );
  const summaryMetrics = summaryMetricDefinitions.map((definition) => {
    const metricValue = summaryMetricValues.get(definition.key);
    return {
      ...definition,
      value: metricValue?.value ?? "-",
      footerValue: metricValue?.footerValue,
    };
  });

  return (
    <main className={styles.cronOverviewPage}>
      {loading ? <div className={styles.loadingBar}>加载中...</div> : null}
      <header className={styles.header}>
        <div className={styles.titleRow}>
          <h1>定时任务概览</h1>
        </div>
        <div className={styles.toolbar}>
          <div className={styles.toolbarLeft}>
            <div className={styles.segmentedControl}>
              <button
                type="button"
                className={timeRange === "day" ? styles.segmentActive : styles.segmentButton}
                onClick={() => handleModeChange("day")}
              >
                今天
              </button>
              <button
                type="button"
                className={timeRange === "week" ? styles.segmentActive : styles.segmentButton}
                onClick={() => handleModeChange("week")}
              >
                近7天
              </button>
              <button
                type="button"
                className={timeRange === "month" ? styles.segmentActive : styles.segmentButton}
                onClick={() => handleModeChange("month")}
              >
                近30天
              </button>
            </div>

            <div className={styles.dateRangePanel}>
              <DatePicker.RangePicker
                className={styles.rangePicker}
                value={dateRange}
                onChange={handleDateRangeChange}
                format="YYYY-MM-DD"
                suffixIcon={<CalendarDays size={16} />}
                disabledDate={disabledDate}
                allowClear={false}
              />
            </div>
          </div>

          <div className={styles.toolbarRight}>
            <Select
              className={styles.scopeSelect}
              mode="multiple"
              value={bbkIds}
              onChange={setBbkIds}
              placeholder="全部分行"
              maxTagCount="responsive"
              maxTagPlaceholder={(omittedValues) => (
                <Tooltip
                  title={omittedValues
                    .map((item) => {
                      const value = String(item.value ?? "");
                      return BBK_ID_TO_NAME_MAP[value] || value;
                    })
                    .join("、")}
                >
                  <span>+{omittedValues.length} 个分行</span>
                </Tooltip>
              )}
              allowClear
              showSearch
              filterOption={(input, option) => {
                const searchValue = input.toLowerCase();
                const optionValue = String(option?.value ?? "");
                const optionLabel = BBK_ID_TO_NAME_MAP[optionValue] || "";
                return (
                  optionValue.toLowerCase().includes(searchValue) ||
                  optionLabel.toLowerCase().includes(searchValue)
                );
              }}
            >
              {BBK_ID_MAP.map((item) => (
                <Option key={item.value} value={item.value}>
                  {item.label}
                </Option>
              ))}
            </Select>
            <button
              type="button"
              className={styles.refreshButton}
              onClick={fetchOverview}
            >
              <RefreshCw size={16} />
              刷新
            </button>
          </div>
        </div>
      </header>

      <section className={styles.summaryGrid} aria-label="概览指标">
        {summaryMetrics.map((metric) => (
          <SummaryCard key={metric.key} metric={metric} />
        ))}
      </section>

      <p className={styles.formulaNote}>
        说明： 执行成功率 = 成功执行数 / 定时任务数； 已读率 = 已读任务数 / 定时报任务数； 报错率 = 报错执行次数 / 任务执行次数
      </p>

      <BehaviorTable data={overviewData.branchBehaviorRows} />

      <section className={styles.anomalySection}>
        <div className={styles.anomalyLeft}>
          <h2>分行层异常诊断</h2>
          <div className={styles.miniSummaryGrid}>
            <MiniSummaryCard
              icon={Banknote}
              title="受影响分行数"
              value={overviewData.anomalySummary.affectedBranches}
              unit={overviewData.anomalySummary.affectedBranchesUnit}
            />
            <MiniSummaryCard
              icon={UserRoundCheck}
              title="受影响客户经理数"
              value={overviewData.anomalySummary.affectedManagers}
              unit={overviewData.anomalySummary.affectedManagersUnit}
            />
          </div>
          <FailureReasonPanel data={overviewData.failureReasons} />
        </div>
        <RankTable data={overviewData.anomalyRankRows} />
      </section>
    </main>
  );
}
