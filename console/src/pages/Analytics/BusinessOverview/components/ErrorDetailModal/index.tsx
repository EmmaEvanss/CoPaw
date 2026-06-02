import { useCallback, useEffect, useRef, useState } from "react";
import { Modal, message, Select, Input, Spin, Tooltip } from "antd";
import { AlertTriangle, Copy, ExternalLink } from "lucide-react";
import {
  tracingApi,
  type ErrorItem,
  type ErrorListResponse,
  type TraceDetail,
} from "../../../../../api/modules/tracing";
import { getBbkDisplayName } from "../../../../../constants/bbk";
import styles from "./index.module.less";

interface ErrorDetailModalProps {
  open: boolean;
  startDate: string;
  endDate: string;
  bbkIds?: string;
  onClose: () => void;
}

const formatTime = (time: string | null) => {
  if (!time) return "-";
  const date = new Date(time);
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
};

const formatDuration = (ms: number | null | undefined) => {
  if (!ms) return "-";
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}m`;
};

const formatTokens = (tokens: number | null | undefined) => {
  if (!tokens) return "0";
  if (tokens < 1000) return tokens.toString();
  if (tokens < 1000000) return `${(tokens / 1000).toFixed(1)}K`;
  return `${(tokens / 1000000).toFixed(1)}M`;
};

const truncateText = (text: string, maxLen: number) => {
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen) + "...";
};

const truncateId = (id: string) => {
  if (id.length <= 16) return id;
  return id.slice(0, 16) + "...";
};

export default function ErrorDetailModal({
  open,
  startDate,
  endDate,
  bbkIds,
  onClose,
}: ErrorDetailModalProps) {
  const [errors, setErrors] = useState<ErrorItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const loadingRef = useRef(false);

  const [errorType, setErrorType] = useState<string>("all");
  const [searchText, setSearchText] = useState("");

  const [selectedError, setSelectedError] = useState<ErrorItem | null>(null);
  const [traceDetail, setTraceDetail] = useState<TraceDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // 使用 ref 跟踪是否需要自动选中第一个
  const shouldAutoSelect = useRef(true);

  const fetchErrors = useCallback(
    async (pageNum: number, append: boolean = false) => {
      if (loadingRef.current) return;
      loadingRef.current = true;

      if (append) {
        setLoadingMore(true);
      } else {
        setLoading(true);
      }

      try {
        const result = await tracingApi.getErrorList(pageNum, pageSize, {
          start_date: startDate,
          end_date: endDate,
          bbk_ids: bbkIds,
          error_type: errorType === "all" ? undefined : errorType,
          search: searchText || undefined,
        });

        if (append) {
          setErrors(prev => [...prev, ...(result.items || [])]);
        } else {
          setErrors(result.items || []);
        }
        setTotal(result.total || 0);
        setHasMore((result.items || []).length >= pageSize);

        // 默认选中第一个（仅在初始化时）
        if (!append && result.items && result.items.length > 0 && shouldAutoSelect.current) {
          setSelectedError(result.items[0]);
          shouldAutoSelect.current = false;
        }
      } catch (error) {
        console.error("Failed to fetch error list:", error);
        message.error("获取错误列表失败");
      } finally {
        setLoading(false);
        setLoadingMore(false);
        loadingRef.current = false;
      }
    },
    [startDate, endDate, bbkIds, errorType, searchText, pageSize],
  );

  const handleScroll = useCallback(
    (e: React.UIEvent<HTMLDivElement>) => {
      const target = e.currentTarget;
      const scrollBottom = target.scrollHeight - target.scrollTop - target.clientHeight;

      if (scrollBottom < 40 && hasMore && !loadingRef.current) {
        const nextPage = page + 1;
        setPage(nextPage);
        fetchErrors(nextPage, true);
      }
    },
    [page, hasMore, fetchErrors],
  );

  const fetchTraceDetail = useCallback(async (traceId: string) => {
    setDetailLoading(true);
    try {
      const detail = await tracingApi.getTraceDetail(traceId);
      setTraceDetail(detail);
    } catch (error) {
      console.error("Failed to fetch trace detail:", error);
      message.error("获取对话详情失败");
    } finally {
      setDetailLoading(false);
    }
  }, []);

  // 重置并加载新数据（当筛选条件变化时）
  useEffect(() => {
    if (open) {
      shouldAutoSelect.current = true;
      setErrors([]);
      setPage(1);
      setHasMore(true);
      setSelectedError(null);
      setTraceDetail(null);
      fetchErrors(1, false);
    }
  }, [open, fetchErrors]);

  useEffect(() => {
    if (selectedError) {
      fetchTraceDetail(selectedError.trace_id);
    }
  }, [selectedError, fetchTraceDetail]);

  const handleClose = () => {
    shouldAutoSelect.current = true;
    setErrors([]);
    setTotal(0);
    setPage(1);
    setHasMore(true);
    setSelectedError(null);
    setTraceDetail(null);
    setErrorType("all");
    setSearchText("");
    onClose();
  };

  const handleSelectError = (error: ErrorItem) => {
    setSelectedError(error);
  };

  const handleCopyTraceId = async () => {
    if (!selectedError) return;
    try {
      await navigator.clipboard.writeText(selectedError.trace_id);
      message.success("Trace ID 已复制");
    } catch {
      message.error("复制失败");
    }
  };

  const totalInputTokens = traceDetail?.trace.total_input_tokens ?? 0;
  const totalOutputTokens = traceDetail?.trace.total_output_tokens ?? 0;

  return (
    <Modal
      title={
        <span>
          <AlertTriangle size={18} style={{ marginRight: 8, color: "#ef4444" }} />
          报错详情
        </span>
      }
      open={open}
      onCancel={handleClose}
      width="100vw"
      footer={null}
      destroyOnClose
      className={styles.errorDetailModal}
      classNames={{ body: styles.errorDetailModalBody }}
      style={{ top: 0, paddingBottom: 0 }}
    >
      <div className={styles.modalContent}>
        {/* 左侧：错误列表 */}
        <div className={styles.leftPanel}>
          {/* 固定的头部区域 */}
          <div className={styles.leftPanelHeader}>
            <div className={styles.errorListHeader}>
              <div className={styles.errorListTitle}>错误列表</div>
              <span className={styles.errorListCount}>共 {total} 条</span>
            </div>

            <div className={styles.errorListFilters}>
              <Select
                value={errorType}
                onChange={(val) => {
                  setErrorType(val);
                  shouldAutoSelect.current = true;
                  setSelectedError(null);
                }}
                style={{ flex: 1 }}
                options={[
                  { value: "all", label: "全部类型" },
                  { value: "llm_input", label: "模型报错" },
                  { value: "tool_call_end", label: "工具报错" },
                ]}
              />
              <Input
                placeholder="搜索用户/错误"
                value={searchText}
                onChange={(e) => {
                  setSearchText(e.target.value);
                  shouldAutoSelect.current = true;
                  setSelectedError(null);
                }}
                style={{ width: 140 }}
                allowClear
              />
            </div>
          </div>

          {/* 滚动的列表区域 */}
          <div className={styles.errorListScroll} onScroll={handleScroll}>
            {loading && errors.length === 0 ? (
              <div className={styles.errorListLoading}>
                <Spin size="small" />
              </div>
            ) : errors.length === 0 ? (
              <div className={styles.errorListEmpty}>暂无错误记录</div>
            ) : (
              <>
                {errors.map((err) => (
                  <div
                    key={err.span_id}
                    className={`${styles.errorCard} ${
                      selectedError?.span_id === err.span_id ? styles.selected : ""
                    }`}
                    onClick={() => handleSelectError(err)}
                  >
                    <div className={styles.errorCardHeader}>
                      <span
                        className={`${styles.errorTypeTag} ${
                          err.event_type === "llm_input"
                            ? styles.errorTypeTagModel
                            : styles.errorTypeTagTool
                        }`}
                      >
                        {err.event_type === "llm_input" ? "模型报错" : "工具报错"}
                      </span>
                      <span className={styles.errorCardTime}>
                        {formatTime(err.start_time)}
                      </span>
                    </div>
                    <div className={styles.errorCardMessage}>
                      {truncateText(err.error, 50)}
                    </div>
                    <div className={styles.errorCardMeta}>
                      <span>
                        👤 {err.user_name || err.user_id}
                        {err.bbk_id && ` / ${getBbkDisplayName(err.bbk_id)}`}
                      </span>
                      {err.event_type === "llm_input" && err.model_name && (
                        <span>🤖 {err.model_name}</span>
                      )}
                      {err.event_type === "tool_call_end" && err.tool_name && (
                        <span>🔧 {err.tool_name}</span>
                      )}
                    </div>
                    <div className={styles.errorCardTrace}>
                      trace:{" "}
                      <span className={styles.errorTraceId}>
                        {truncateId(err.trace_id)}
                      </span>{" "}
                      | {formatDuration(err.duration_ms)} |{" "}
                      {formatTokens(
                        (err.input_tokens ?? 0) + (err.output_tokens ?? 0),
                      )}{" "}
                      tokens
                    </div>
                  </div>
                ))}
                {loadingMore && (
                  <div className={styles.loadingMore}>加载中...</div>
                )}
              </>
            )}
          </div>
        </div>

        {/* 右侧：对话详情 */}
        <div className={styles.rightPanel}>
          <div className={styles.detailTitle}>对话详情</div>

          {detailLoading ? (
            <div className={styles.detailLoading}>
              <Spin size="small" />
            </div>
          ) : !selectedError ? (
            <div className={styles.detailLoading}>请选择一个错误查看详情</div>
          ) : traceDetail ? (
            <>
              {/* 元信息 */}
              <div className={styles.detailMeta}>
                <div className={styles.detailMetaRow}>
                  <span className={styles.detailMetaItem}>
                    <strong>Trace ID:</strong>
                    <span style={{ color: "#2563eb" }}>
                      {truncateId(traceDetail.trace.trace_id)}
                    </span>
                  </span>
                  <span className={styles.detailMetaItem}>
                    <strong>用户:</strong>
                    {traceDetail.trace.user_name || traceDetail.trace.user_id}
                    {traceDetail.trace.bbk_id &&
                      ` / ${getBbkDisplayName(traceDetail.trace.bbk_id)}`}
                  </span>
                  <span className={styles.detailMetaItem}>
                    <strong>状态:</strong>
                    <span style={{ color: "#ef4444" }}>
                      {traceDetail.trace.status}
                    </span>
                  </span>
                </div>
                <div className={styles.detailMetaRow}>
                  <span className={styles.detailMetaItem}>
                    <strong>时长:</strong>{" "}
                    {formatDuration(traceDetail.trace.duration_ms)}
                  </span>
                  <span className={styles.detailMetaItem}>
                    <strong>Token:</strong>{" "}
                    {formatTokens(totalInputTokens + totalOutputTokens)}
                    (输入 {formatTokens(totalInputTokens)} / 输出{" "}
                    {formatTokens(totalOutputTokens)})
                  </span>
                  {traceDetail.trace.model_name && (
                    <span className={styles.detailMetaItem}>
                      <strong>模型:</strong> {traceDetail.trace.model_name}
                    </span>
                  )}
                </div>
                <div className={styles.detailErrorBox}>
                  <strong>⚠️ 错误信息:</strong> {selectedError.error}
                </div>
              </div>

              {/* 对话内容 */}
              <div className={styles.detailContent}>
                {traceDetail.trace.user_message && (
                  <div className={styles.messageBlock}>
                    <div className={styles.messageLabel}>
                      <span>👤 用户消息</span>
                      <span>{formatTime(traceDetail.trace.start_time)}</span>
                    </div>
                    <div className={`${styles.messageContent} ${styles.userMessage}`}>
                      {truncateText(traceDetail.trace.user_message, 500)}
                    </div>
                  </div>
                )}

                <div className={styles.messageBlock}>
                  <div className={styles.messageLabel}>
                    <span>🤖 模型响应</span>
                  </div>
                  <div className={`${styles.messageContent} ${styles.modelOutput}`}>
                    <div className={styles.modelError}>
                      ❌ 报错: {selectedError.error}
                    </div>
                    {traceDetail.trace.model_output ? (
                      <div>{truncateText(traceDetail.trace.model_output, 500)}</div>
                    ) : (
                      <div style={{ color: "#666" }}>
                        模型调用失败，未生成响应内容
                      </div>
                    )}
                  </div>
                </div>

                {/* 调用链路 */}
                <div className={styles.callChain}>
                  <div className={styles.callChainLabel}>调用链路</div>
                  <div className={styles.callChainTags}>
                    {traceDetail.trace.model_name && (
                      <span className={styles.callChainTag}>
                        {traceDetail.trace.model_name}
                      </span>
                    )}
                    <span
                      className={`${styles.callChainTag} ${styles.callChainTagError}`}
                    >
                      ❌{" "}
                      {selectedError.event_type === "llm_input"
                        ? "模型报错"
                        : "工具报错"}
                    </span>
                    {traceDetail.trace.tools_used?.map((tool) => (
                      <span key={tool} className={styles.callChainTag}>
                        {tool}
                      </span>
                    ))}
                    {traceDetail.trace.skills_used?.map((skill) => (
                      <span key={skill} className={styles.callChainTag}>
                        {skill}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {/* 操作按钮 */}
              <div className={styles.detailActions}>
                <button
                  type="button"
                  className={`${styles.actionButton} ${styles.primaryButton}`}
                  onClick={handleCopyTraceId}
                >
                  <Copy size={14} style={{ marginRight: 4 }} />
                  复制 Trace ID
                </button>
                <Tooltip title="查看完整 Span 详情">
                  <button
                    type="button"
                    className={`${styles.actionButton} ${styles.secondaryButton}`}
                    onClick={() => {
                      message.info("Span 详情功能待开发");
                    }}
                  >
                    <ExternalLink size={14} style={{ marginRight: 4 }} />
                    查看完整 Span 详情
                  </button>
                </Tooltip>
              </div>
            </>
          ) : null}
        </div>
      </div>
    </Modal>
  );
}