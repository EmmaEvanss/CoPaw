import { useState } from "react";
import { Timeline, Tag, Pagination, Spin, Empty } from "antd";
import { User, Bot, ChevronDown, ChevronUp } from "lucide-react";
import dayjs from "dayjs";
import { tracingApi, TraceListItem, TraceDetail } from "../../../../../api/modules/tracing";
import styles from "./index.module.less";

interface SessionTracesFlowProps {
  traces: TraceListItem[];
  total: number;
  page: number;
  pageSize: number;
  loading: boolean;
  hasSelectedSession: boolean;
  onPageChange: (page: number) => void;
}

export default function SessionTracesFlow({
  traces,
  total,
  page,
  pageSize,
  loading,
  hasSelectedSession,
  onPageChange,
}: SessionTracesFlowProps) {
  const [expandedTraces, setExpandedTraces] = useState<Set<string>>(new Set());
  const [traceDetails, setTraceDetails] = useState<Map<string, TraceDetail>>(new Map());
  const [loadingTraces, setLoadingTraces] = useState<Set<string>>(new Set());

  const formatTokens = (tokens: number) => {
    if (!tokens) return "0";
    if (tokens < 1000) return tokens.toString();
    if (tokens < 1000000) return `${(tokens / 1000).toFixed(1)}K`;
    return `${(tokens / 1000000).toFixed(1)}M`;
  };

  const formatDuration = (ms: number | null) => {
    if (!ms) return "-";
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${(ms / 60000).toFixed(1)}m`;
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "completed":
        return "success";
      case "running":
        return "processing";
      case "error":
        return "error";
      case "cancelled":
        return "default";
      default:
        return "default";
    }
  };

  const handleToggleExpand = async (traceId: string) => {
    const newExpanded = new Set(expandedTraces);

    if (newExpanded.has(traceId)) {
      newExpanded.delete(traceId);
    } else {
      newExpanded.add(traceId);

      // 如果还没有加载详情，则加载
      if (!traceDetails.has(traceId)) {
        setLoadingTraces((prev) => new Set(prev).add(traceId));
        try {
          const detail = await tracingApi.getTraceDetail(traceId);
          setTraceDetails((prev) => new Map(prev).set(traceId, detail));
        } catch (error) {
          console.error("Failed to fetch trace detail:", error);
        } finally {
          setLoadingTraces((prev) => {
            const next = new Set(prev);
            next.delete(traceId);
            return next;
          });
        }
      }
    }

    setExpandedTraces(newExpanded);
  };

  if (loading) {
    return (
      <div className={styles.tracesFlow}>
        <div className={styles.tracesLoading}>
          <Spin />
        </div>
      </div>
    );
  }

  // 未选择会话时显示提示
  if (!hasSelectedSession) {
    return (
      <div className={styles.tracesFlow}>
        <div className={styles.tracesTitle}>对话流</div>
        <Empty description="请选择左侧会话卡片查看对话详情" />
      </div>
    );
  }

  // 已选择会话但无数据
  if (traces.length === 0) {
    return (
      <div className={styles.tracesFlow}>
        <div className={styles.tracesTitle}>对话流</div>
        <Empty description="暂无对话数据" />
      </div>
    );
  }

  return (
    <div className={styles.tracesFlow}>
      <div className={styles.tracesTitle}>对话流</div>

      <Timeline
        items={[...traces].reverse().map((trace) => {
          const isExpanded = expandedTraces.has(trace.trace_id);
          const detail = traceDetails.get(trace.trace_id);
          const isLoading = loadingTraces.has(trace.trace_id);

          return {
            color: trace.status === "error" ? "red" : "blue",
            children: (
              <div className={styles.traceItem}>
                {/* 基础信息 */}
                <div className={styles.traceHeader}>
                  <Tag color={getStatusColor(trace.status)}>{trace.status}</Tag>
                  <span className={styles.traceTime}>
                    {dayjs(trace.start_time).format("MM-DD HH:mm:ss")}
                  </span>
                  <span className={styles.traceDuration}>
                    {formatDuration(trace.duration_ms)}
                  </span>
                </div>

                <div className={styles.traceMeta}>
                  <span>Token: {formatTokens(trace.total_tokens)}</span>
                  {trace.model_name && (
                    <span className={styles.traceModel}>{trace.model_name}</span>
                  )}
                  {trace.skills_count > 0 && (
                    <Tag color="blue" style={{ marginLeft: 4 }}>
                      技能: {trace.skills_count}
                    </Tag>
                  )}
                </div>

                {/* 展开/收起按钮 */}
                <div
                  className={styles.traceExpandBtn}
                  onClick={() => handleToggleExpand(trace.trace_id)}
                >
                  {isLoading ? (
                    <Spin size="small" />
                  ) : isExpanded ? (
                    <>
                      <ChevronUp size={14} />
                      <span>收起详情</span>
                    </>
                  ) : (
                    <>
                      <ChevronDown size={14} />
                      <span>查看详情</span>
                    </>
                  )}
                </div>

                {/* 展开的详情内容 */}
                {isExpanded && detail && (
                  <div className={styles.traceDetail}>
                    {/* 技能使用 */}
                    {detail.trace.skills_used && detail.trace.skills_used.length > 0 && (
                      <div className={styles.skillsSection}>
                        <span className={styles.sectionLabel}>技能使用:</span>
                        <div className={styles.tagList}>
                          {detail.trace.skills_used.map((skill) => (
                            <Tag key={skill} color="blue">
                              {skill}
                            </Tag>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* 用户输入 */}
                    {detail.trace.user_message && (
                      <div className={styles.userMessage}>
                        <div className={styles.messageLabel}>
                          <User size={14} style={{ marginRight: 4 }} />
                          用户输入
                        </div>
                        <div className={styles.messageContent}>
                          {detail.trace.user_message}
                        </div>
                      </div>
                    )}

                    {/* 模型输出 */}
                    {detail.trace.model_output && (
                      <div className={styles.modelOutput}>
                        <div className={styles.messageLabel}>
                          <Bot size={14} style={{ marginRight: 4 }} />
                          模型输出
                        </div>
                        <div className={styles.messageContent}>
                          {detail.trace.model_output}
                        </div>
                      </div>
                    )}

                    {/* 错误信息 */}
                    {detail.trace.error && (
                      <div className={styles.errorSection}>
                        <span className={styles.sectionLabel}>错误信息:</span>
                        <pre className={styles.errorText}>{detail.trace.error}</pre>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ),
          };
        })}
      />

      {total > pageSize && (
        <div className={styles.tracesPagination}>
          <Pagination
            simple
            current={page}
            pageSize={pageSize}
            total={total}
            onChange={onPageChange}
          />
        </div>
      )}
    </div>
  );
}
