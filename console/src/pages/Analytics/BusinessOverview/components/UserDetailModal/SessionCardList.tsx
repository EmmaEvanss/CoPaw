import { Pagination, Spin } from "antd";
import { SessionListItem } from "../../../../../api/modules/tracing";
import styles from "./index.module.less";

interface SessionCardListProps {
  sessions: SessionListItem[];
  total: number;
  page: number;
  pageSize: number;
  loading: boolean;
  selectedSessionId: string | null;
  onSelect: (sessionId: string) => void;
  onPageChange: (page: number) => void;
}

export default function SessionCardList({
  sessions,
  total,
  page,
  pageSize,
  loading,
  selectedSessionId,
  onSelect,
  onPageChange,
}: SessionCardListProps) {
  // 格式化 Token 数量显示
  const formatTokens = (tokens: number) => {
    if (!tokens) return "0";
    if (tokens < 1000) return tokens.toString();
    if (tokens < 1000000) return `${(tokens / 1000).toFixed(1)}K`;
    return `${(tokens / 1000000).toFixed(1)}M`;
  };

  // 格式化时间显示
  const formatTime = (time: string | null) => {
    if (!time) return "-";
    return new Date(time).toLocaleString("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  // 截断会话 ID 显示
  const truncateId = (id: string) => {
    if (id.length <= 16) return id;
    return id.slice(0, 16) + "...";
  };

  return (
    <div className={styles.sessionList}>
      <div className={styles.sessionListTitle}>会话列表</div>

      {loading ? (
        <div className={styles.sessionLoading}>
          <Spin size="small" />
        </div>
      ) : sessions.length === 0 ? (
        <div className={styles.sessionEmpty}>暂无会话数据</div>
      ) : (
        <>
          {sessions.map((session) => (
            <div
              key={session.session_id}
              className={`${styles.sessionCard} ${
                selectedSessionId === session.session_id ? styles.selected : ""
              }`}
              onClick={() => onSelect(session.session_id)}
            >
              <div className={styles.sessionId}>
                {truncateId(session.session_id)}
              </div>
              <div className={styles.sessionMeta}>
                <span>渠道: {session.channel || "-"}</span>
                <span>对话: {session.total_traces}</span>
              </div>
              <div className={styles.sessionStats}>
                <span>Token: {formatTokens(session.total_tokens)}</span>
                <span>技能: {session.total_skills}</span>
              </div>
              <div className={styles.sessionTime}>
                {formatTime(session.last_active)}
              </div>
            </div>
          ))}

          {total > pageSize && (
            <div className={styles.sessionPagination}>
              <Pagination
                simple
                current={page}
                pageSize={pageSize}
                total={total}
                onChange={onPageChange}
              />
            </div>
          )}
        </>
      )}
    </div>
  );
}
