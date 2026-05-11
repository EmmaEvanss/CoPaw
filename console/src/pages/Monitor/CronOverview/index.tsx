import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import {
  Tabs,
  Card,
  Table,
  Input,
  Select,
  DatePicker,
  Button,
  Space,
  Tag,
  Drawer,
  Descriptions,
  message,
  Spin,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import dayjs from "dayjs";
import { DownloadOutlined, EyeOutlined, SearchOutlined } from "@ant-design/icons";
import { PageHeader } from "@/components/PageHeader";
import { monitorApi, CronJobItem, ExecutionItem } from "../../../api/modules/monitor";
import styles from "./index.module.less";

const { RangePicker } = DatePicker;

// Status colors
const JOB_STATUS_COLORS: Record<string, string> = {
  active: "green",
  paused: "orange",
  deleted: "red",
};

const EXEC_STATUS_COLORS: Record<string, string> = {
  success: "green",
  error: "red",
  cancelled: "orange",
  timeout: "orange",
  skipped: "default",
  running: "blue",
};

// Status translations
const JOB_STATUS_LABELS: Record<string, string> = {
  active: "运行中",
  paused: "已暂停",
  deleted: "已删除",
};

const EXEC_STATUS_LABELS: Record<string, string> = {
  success: "成功",
  error: "失败",
  cancelled: "取消",
  timeout: "超时",
  skipped: "跳过",
  running: "运行中",
};

export default function CronOverviewPage() {
  const { t } = useTranslation();

  // Jobs state
  const [jobsLoading, setJobsLoading] = useState(false);
  const [jobs, setJobs] = useState<CronJobItem[]>([]);
  const [jobsTotal, setJobsTotal] = useState(0);
  const [jobsPage, setJobsPage] = useState(1);
  const [jobsPageSize, setJobsPageSize] = useState(10);
  const [jobsTenantFilter, setJobsTenantFilter] = useState<string>("");
  const [jobsBbkFilter, setJobsBbkFilter] = useState<string>("");
  const [jobsSourceFilter, setJobsSourceFilter] = useState<string>("");
  const [jobsEnabledFilter, setJobsEnabledFilter] = useState<string>("");

  // Executions state
  const [execsLoading, setExecsLoading] = useState(false);
  const [executions, setExecutions] = useState<ExecutionItem[]>([]);
  const [execsTotal, setExecsTotal] = useState(0);
  const [execsPage, setExecsPage] = useState(1);
  const [execsPageSize, setExecsPageSize] = useState(10);
  const [execsJobIdFilter, setExecsJobIdFilter] = useState<string>("");
  const [execsTenantFilter, setExecsTenantFilter] = useState<string>("");
  const [execsStatusFilter, setExecsStatusFilter] = useState<string>("");
  const [execsTimeRange, setExecsTimeRange] = useState<[dayjs.Dayjs | null, dayjs.Dayjs | null]>([
    dayjs().subtract(7, "day"),
    dayjs(),
  ]);

  // Execution detail drawer
  const [detailDrawerOpen, setDetailDrawerOpen] = useState(false);
  const [selectedExecution, setSelectedExecution] = useState<ExecutionItem | null>(null);

  // Fetch jobs
  const fetchJobs = async () => {
    setJobsLoading(true);
    try {
      const result = await monitorApi.getJobs(jobsPage, jobsPageSize, {
        tenant_id: jobsTenantFilter || undefined,
        bbk_id: jobsBbkFilter || undefined,
        source_id: jobsSourceFilter || undefined,
        enabled: jobsEnabledFilter === "" ? undefined : jobsEnabledFilter === "true",
      });
      setJobs(result.items);
      setJobsTotal(result.total);
    } catch (error) {
      console.error("Failed to fetch jobs:", error);
      message.error("获取任务列表失败");
    } finally {
      setJobsLoading(false);
    }
  };

  // Fetch executions
  const fetchExecutions = async () => {
    setExecsLoading(true);
    try {
      const result = await monitorApi.getExecutions(execsPage, execsPageSize, {
        job_id: execsJobIdFilter || undefined,
        tenant_id: execsTenantFilter || undefined,
        status: execsStatusFilter || undefined,
        start_time: execsTimeRange[0]?.format("YYYY-MM-DDTHH:mm:ss") || undefined,
        end_time: execsTimeRange[1]?.format("YYYY-MM-DDTHH:mm:ss") || undefined,
      });
      setExecutions(result.items);
      setExecsTotal(result.total);
    } catch (error) {
      console.error("Failed to fetch executions:", error);
      message.error("获取执行历史失败");
    } finally {
      setExecsLoading(false);
    }
  };

  // Handler for jobs search button - reset page and fetch
  const handleJobsSearch = () => {
    if (jobsPage !== 1) {
      setJobsPage(1);
    } else {
      fetchJobs();
    }
  };

  // Handler for executions search button - reset page and fetch
  const handleExecsSearch = () => {
    if (execsPage !== 1) {
      setExecsPage(1);
    } else {
      fetchExecutions();
    }
  };

  // Jobs query effect - fetch on mount and when page changes
  useEffect(() => {
    fetchJobs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobsPage, jobsPageSize]);

  // Executions query effect - fetch on mount and when page changes
  useEffect(() => {
    fetchExecutions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [execsPage, execsPageSize]);

  // Export jobs
  const handleExportJobs = async () => {
    try {
      message.loading("正在导出...");
      const blob = await monitorApi.exportJobs({
        tenant_id: jobsTenantFilter || undefined,
        bbk_id: jobsBbkFilter || undefined,
        source_id: jobsSourceFilter || undefined,
        enabled: jobsEnabledFilter === "" ? undefined : jobsEnabledFilter === "true",
      });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `cron_jobs_${dayjs().format("YYYY-MM-DD_HHmmss")}.xlsx`;
      a.click();
      window.URL.revokeObjectURL(url);
      message.success("导出成功");
    } catch (error) {
      console.error("Export failed:", error);
      message.error("导出失败");
    }
  };

  // Export executions
  const handleExportExecutions = async () => {
    try {
      message.loading("正在导出...");
      const blob = await monitorApi.exportExecutions({
        job_id: execsJobIdFilter || undefined,
        tenant_id: execsTenantFilter || undefined,
        status: execsStatusFilter || undefined,
        start_time: execsTimeRange[0]?.format("YYYY-MM-DDTHH:mm:ss") || undefined,
        end_time: execsTimeRange[1]?.format("YYYY-MM-DDTHH:mm:ss") || undefined,
      });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `cron_executions_${dayjs().format("YYYY-MM-DD_HHmmss")}.xlsx`;
      a.click();
      window.URL.revokeObjectURL(url);
      message.success("导出成功");
    } catch (error) {
      console.error("Export failed:", error);
      message.error("导出失败");
    }
  };

  // View execution detail
  const handleViewExecution = (exec: ExecutionItem) => {
    setSelectedExecution(exec);
    setDetailDrawerOpen(true);
  };

  // Jobs table columns
  const jobsColumns: ColumnsType<CronJobItem> = [
    {
      title: "任务ID",
      dataIndex: "id",
      key: "id",
      width: 280,
      ellipsis: true,
    },
    {
      title: "任务名称",
      dataIndex: "name",
      key: "name",
      width: 200,
    },
    {
      title: "租户ID",
      dataIndex: "tenant_id",
      key: "tenant_id",
      width: 150,
    },
    {
      title: "分行号",
      dataIndex: "bbk_id",
      key: "bbk_id",
      width: 120,
    },
    {
      title: "来源标识",
      dataIndex: "source_id",
      key: "source_id",
      width: 120,
    },
    {
      title: "启用",
      dataIndex: "enabled",
      key: "enabled",
      width: 80,
      render: (enabled: boolean) => (
        <Tag color={enabled ? "green" : "default"}>
          {enabled ? "是" : "否"}
        </Tag>
      ),
    },
    {
      title: "类型",
      dataIndex: "task_type",
      key: "task_type",
      width: 80,
    },
    {
      title: "已执行次数",
      dataIndex: "execution_count",
      key: "execution_count",
      width: 100,
      render: (count: number) => count || 0,
    },
    {
      title: "Cron表达式",
      dataIndex: "cron_expr",
      key: "cron_expr",
      width: 150,
    },
    {
      title: "创建者",
      dataIndex: "creator_user_id",
      key: "creator_user_id",
      width: 150,
      ellipsis: true,
    },
    {
      title: "创建时间",
      dataIndex: "created_at",
      key: "created_at",
      width: 180,
      render: (time: string | null) =>
        time ? dayjs(time).format("YYYY-MM-DD HH:mm:ss") : "-",
    },
  ];

  // Executions table columns
  const execsColumns: ColumnsType<ExecutionItem> = [
    {
      title: "记录ID",
      dataIndex: "id",
      key: "id",
      width: 80,
    },
    {
      title: "任务ID",
      dataIndex: "job_id",
      key: "job_id",
      width: 280,
      ellipsis: true,
    },
    {
      title: "任务名称",
      dataIndex: "job_name",
      key: "job_name",
      width: 200,
      ellipsis: true,
    },
    {
      title: "租户ID",
      dataIndex: "tenant_id",
      key: "tenant_id",
      width: 150,
    },
    {
      title: "执行状态",
      dataIndex: "status",
      key: "status",
      width: 100,
      render: (status: string) => (
        <Tag color={EXEC_STATUS_COLORS[status] || "default"}>
          {EXEC_STATUS_LABELS[status] || status}
        </Tag>
      ),
    },
    {
      title: "执行时间",
      dataIndex: "actual_time",
      key: "actual_time",
      width: 180,
      render: (time: string) => dayjs(time).format("YYYY-MM-DD HH:mm:ss"),
    },
    {
      title: "耗时(ms)",
      dataIndex: "duration_ms",
      key: "duration_ms",
      width: 100,
    },
    {
      title: "手动执行",
      dataIndex: "is_manual",
      key: "is_manual",
      width: 80,
      render: (manual: boolean) => manual ? "是" : "否",
    },
    {
      title: "Trace ID",
      dataIndex: "trace_id",
      key: "trace_id",
      width: 200,
      ellipsis: true,
    },
    {
      title: "操作",
      key: "action",
      width: 80,
      render: (_, record) => (
        <Button
          type="link"
          size="small"
          icon={<EyeOutlined />}
          onClick={() => handleViewExecution(record)}
        >
          详情
        </Button>
      ),
    },
  ];

  return (
    <div className={styles.cronOverviewPage}>
      <PageHeader
        items={[
          { title: t("nav.monitor") || "监控" },
          { title: "定时任务概览" },
        ]}
      />

      <Card className={styles.tableCard}>
        <Tabs
          defaultActiveKey="jobs"
          items={[
            {
              key: "jobs",
              label: "任务定义",
              children: (
                <>
                  <div className={styles.filterBar}>
                    <Space size="middle" wrap>
                      <Input
                        placeholder="租户ID"
                        value={jobsTenantFilter}
                        onChange={(e) => setJobsTenantFilter(e.target.value)}
                        style={{ width: 150 }}
                        allowClear
                      />
                      <Input
                        placeholder="分行号"
                        value={jobsBbkFilter}
                        onChange={(e) => setJobsBbkFilter(e.target.value)}
                        style={{ width: 120 }}
                        allowClear
                      />
                      <Input
                        placeholder="来源标识"
                        value={jobsSourceFilter}
                        onChange={(e) => setJobsSourceFilter(e.target.value)}
                        style={{ width: 120 }}
                        allowClear
                      />
                      <Select
                        placeholder="是否启用"
                        value={jobsEnabledFilter || undefined}
                        onChange={(value) => setJobsEnabledFilter(value || "")}
                        style={{ width: 120 }}
                        allowClear
                        options={[
                          { value: "true", label: "已启用" },
                          { value: "false", label: "未启用" },
                        ]}
                      />
                      <Button
                        type="primary"
                        icon={<SearchOutlined />}
                        onClick={handleJobsSearch}
                      >
                        查询
                      </Button>
                      <Button
                        icon={<DownloadOutlined />}
                        onClick={handleExportJobs}
                      >
                        导出 Excel
                      </Button>
                    </Space>
                  </div>

                  <Table
                    columns={jobsColumns}
                    dataSource={jobs}
                    rowKey="id"
                    loading={jobsLoading}
                    pagination={{
                      current: jobsPage,
                      pageSize: jobsPageSize,
                      total: jobsTotal,
                      showSizeChanger: true,
                      showTotal: (total) => `共 ${total} 条`,
                      onChange: (page, pageSize) => {
                        setJobsPage(page);
                        setJobsPageSize(pageSize);
                      },
                    }}
                    scroll={{ x: 1700 }}
                  />
                </>
              ),
            },
            {
              key: "executions",
              label: "执行历史",
              children: (
                <>
                  <div className={styles.filterBar}>
                    <Space size="middle" wrap>
                      <Input
                        placeholder="任务ID"
                        value={execsJobIdFilter}
                        onChange={(e) => setExecsJobIdFilter(e.target.value)}
                        style={{ width: 280 }}
                        allowClear
                      />
                      <Input
                        placeholder="租户ID"
                        value={execsTenantFilter}
                        onChange={(e) => setExecsTenantFilter(e.target.value)}
                        style={{ width: 150 }}
                        allowClear
                      />
                      <Select
                        placeholder="执行状态"
                        value={execsStatusFilter || undefined}
                        onChange={(value) => setExecsStatusFilter(value || "")}
                        style={{ width: 120 }}
                        allowClear
                        options={[
                          { value: "success", label: "成功" },
                          { value: "error", label: "失败" },
                          { value: "cancelled", label: "取消" },
                          { value: "timeout", label: "超时" },
                          { value: "skipped", label: "跳过" },
                        ]}
                      />
                      <RangePicker
                        value={execsTimeRange as [dayjs.Dayjs, dayjs.Dayjs]}
                        onChange={(dates) =>
                          setExecsTimeRange(dates as [dayjs.Dayjs | null, dayjs.Dayjs | null])
                        }
                      />
                      <Button
                        type="primary"
                        icon={<SearchOutlined />}
                        onClick={handleExecsSearch}
                      >
                        查询
                      </Button>
                      <Button
                        icon={<DownloadOutlined />}
                        onClick={handleExportExecutions}
                      >
                        导出 Excel
                      </Button>
                    </Space>
                  </div>

                  <Table
                    columns={execsColumns}
                    dataSource={executions}
                    rowKey="id"
                    loading={execsLoading}
                    pagination={{
                      current: execsPage,
                      pageSize: execsPageSize,
                      total: execsTotal,
                      showSizeChanger: true,
                      showTotal: (total) => `共 ${total} 条`,
                      onChange: (page, pageSize) => {
                        setExecsPage(page);
                        setExecsPageSize(pageSize);
                      },
                    }}
                    scroll={{ x: 1480 }}
                  />
                </>
              ),
            },
          ]}
        />
      </Card>

      <Drawer
        title="执行详情"
        placement="right"
        width={600}
        open={detailDrawerOpen}
        onClose={() => setDetailDrawerOpen(false)}
      >
        {selectedExecution && (
          <Descriptions column={2} bordered size="small">
            <Descriptions.Item label="记录ID">{selectedExecution.id}</Descriptions.Item>
            <Descriptions.Item label="任务ID">{selectedExecution.job_id}</Descriptions.Item>
            <Descriptions.Item label="任务名称">{selectedExecution.job_name}</Descriptions.Item>
            <Descriptions.Item label="租户ID">{selectedExecution.tenant_id}</Descriptions.Item>
            <Descriptions.Item label="执行状态">
              <Tag color={EXEC_STATUS_COLORS[selectedExecution.status]}>
                {EXEC_STATUS_LABELS[selectedExecution.status]}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="耗时">{selectedExecution.duration_ms}ms</Descriptions.Item>
            <Descriptions.Item label="计划时间">
              {selectedExecution.scheduled_time
                ? dayjs(selectedExecution.scheduled_time).format("YYYY-MM-DD HH:mm:ss")
                : "-"}
            </Descriptions.Item>
            <Descriptions.Item label="实际时间">
              {dayjs(selectedExecution.actual_time).format("YYYY-MM-DD HH:mm:ss")}
            </Descriptions.Item>
            <Descriptions.Item label="结束时间">
              {selectedExecution.end_time
                ? dayjs(selectedExecution.end_time).format("YYYY-MM-DD HH:mm:ss")
                : "-"}
            </Descriptions.Item>
            <Descriptions.Item label="手动执行">
              {selectedExecution.is_manual ? "是" : "否"}
            </Descriptions.Item>
            <Descriptions.Item label="Trace ID" span={2}>
              {selectedExecution.trace_id || "-"}
            </Descriptions.Item>
            <Descriptions.Item label="Session ID" span={2}>
              {selectedExecution.session_id || "-"}
            </Descriptions.Item>
            <Descriptions.Item label="输出预览" span={2}>
              {selectedExecution.output_preview || "-"}
            </Descriptions.Item>
            <Descriptions.Item label="错误信息" span={2}>
              {selectedExecution.error_message || "-"}
            </Descriptions.Item>
          </Descriptions>
        )}
      </Drawer>
    </div>
  );
}