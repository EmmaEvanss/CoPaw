import { Card, Statistic } from "antd";
import {
  HistoryOutlined,
  CheckCircleOutlined,
  DatabaseOutlined,
  FileTextOutlined,
  ClockCircleOutlined,
  HourglassOutlined,
} from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import type { DreamLogsStats } from "../../../../api/types/dreamLogs";
import styles from "../index.module.less";

interface StatsCardsProps {
  stats: DreamLogsStats;
}

const formatSize = (bytes: number): string => {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
};

const formatDuration = (ms: number): string => {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}min`;
};

const formatLastExecution = (timestamp?: string): string => {
  if (!timestamp) return "-";
  const date = new Date(timestamp);
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  return `${month}-${day} ${hours}:${minutes}`;
};

export default function StatsCards({ stats }: StatsCardsProps) {
  const { t } = useTranslation();

  const successRate =
    stats.total_executions > 0
      ? ((stats.success_count / stats.total_executions) * 100).toFixed(1)
      : "0";

  const statItems = [
    {
      key: "totalExecutions",
      title: t("dreamLogs.stats.totalExecutions"),
      value: stats.total_executions,
      icon: <HistoryOutlined />,
      iconBg: "#f0f5ff",
      iconColor: "#4f46e5",
    },
    {
      key: "successRate",
      title: t("dreamLogs.stats.successRate"),
      value: successRate,
      suffix: "%",
      icon: <CheckCircleOutlined />,
      iconBg: "#ecfdf5",
      iconColor: "#059669",
      valueStyle: { color: "#059669" },
    },
    {
      key: "spaceSaved",
      title: t("dreamLogs.stats.spaceSaved"),
      value: formatSize(stats.total_size_saved),
      icon: <DatabaseOutlined />,
      iconBg: "#eef2ff",
      iconColor: "#4f46e5",
    },
    {
      key: "filesChanged",
      title: t("dreamLogs.stats.filesChanged"),
      value: stats.total_files_changed,
      icon: <FileTextOutlined />,
      iconBg: "#fef3c7",
      iconColor: "#d97706",
    },
    {
      key: "avgDuration",
      title: t("dreamLogs.stats.avgDuration"),
      value: formatDuration(stats.avg_duration_ms),
      icon: <HourglassOutlined />,
      iconBg: "#fce7f3",
      iconColor: "#db2777",
    },
    {
      key: "lastOptimization",
      title: t("dreamLogs.stats.lastOptimization"),
      value: formatLastExecution(stats.last_execution),
      icon: <ClockCircleOutlined />,
      iconBg: "#f0fdf4",
      iconColor: "#16a34a",
    },
  ];

  return (
    <div className={styles.statsGrid}>
      {statItems.map((item) => (
        <Card key={item.key} className={styles.statsCard}>
          <div className={styles.statContent}>
            <div
              className={styles.statIconCircle}
              style={{ background: item.iconBg, color: item.iconColor }}
            >
              {item.icon}
            </div>
            <Statistic
              title={item.title}
              value={item.value}
              suffix={item.suffix}
              valueStyle={item.valueStyle}
              className={styles.statValue}
            />
          </div>
        </Card>
      ))}
    </div>
  );
}
