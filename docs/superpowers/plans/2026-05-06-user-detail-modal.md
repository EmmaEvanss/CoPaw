# 用户详情弹窗实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在运营看板热门用户表格中点击用户，弹出 Modal 展示用户统计、会话列表和对话流详情。

**Architecture:** 创建 UserDetailModal 容器组件管理状态，拆分为 UserStatsHeader、SessionCardList、SessionTracesFlow 三个子组件。复用现有 tracing API 和 Descriptions/Tag/Timeline 组件。

**Tech Stack:** React、Ant Design (Modal、Descriptions、Tag、Timeline、Pagination)、TypeScript、Less

---

## Task 1: 创建组件目录和类型定义

**Files:**
- Create: `console/src/pages/Analytics/BusinessOverview/components/UserDetailModal/index.tsx`
- Create: `console/src/pages/Analytics/BusinessOverview/components/UserDetailModal/index.module.less`
- Modify: `console/src/pages/Analytics/BusinessOverview/types.ts`

- [ ] **Step 1: 创建组件目录结构**

```bash
mkdir -p "console/src/pages/Analytics/BusinessOverview/components/UserDetailModal"
```

- [ ] **Step 2: 在 types.ts 中添加 Modal 状态类型**

在 `console/src/pages/Analytics/BusinessOverview/types.ts` 文件末尾添加：

```typescript
// 用户详情 Modal 状态类型
export interface UserDetailModalProps {
  open: boolean;
  userId: string | null;
  startDate?: string;
  endDate?: string;
  sourceId?: string;
  onClose: () => void;
}
```

- [ ] **Step 3: 提交**

```bash
git add console/src/pages/Analytics/BusinessOverview/types.ts
git commit -m "feat(business-overview): add UserDetailModal type definition"
```

---

## Task 2: 创建 UserDetailModal 容器组件

**Files:**
- Create: `console/src/pages/Analytics/BusinessOverview/components/UserDetailModal/index.tsx`
- Create: `console/src/pages/Analytics/BusinessOverview/components/UserDetailModal/index.module.less`

- [ ] **Step 1: 创建 Modal 容器组件骨架**

创建文件 `console/src/pages/Analytics/BusinessOverview/components/UserDetailModal/index.tsx`：

```tsx
import { useState, useEffect, useCallback } from "react";
import { Modal, Spin, Empty } from "antd";
import { User } from "lucide-react";
import {
  tracingApi,
  UserStats,
  SessionListItem,
  TraceListItem,
} from "../../../../../api/modules/tracing";
import { UserDetailModalProps } from "../../types";
import UserStatsHeader from "./UserStatsHeader";
import SessionCardList from "./SessionCardList";
import SessionTracesFlow from "./SessionTracesFlow";
import styles from "./index.module.less";

export default function UserDetailModal({
  open,
  userId,
  startDate,
  endDate,
  sourceId,
  onClose,
}: UserDetailModalProps) {
  // 用户统计状态
  const [userStats, setUserStats] = useState<UserStats | null>(null);
  const [userLoading, setUserLoading] = useState(false);

  // 会话列表状态
  const [sessions, setSessions] = useState<SessionListItem[]>([]);
  const [sessionsTotal, setSessionsTotal] = useState(0);
  const [sessionsPage, setSessionsPage] = useState(1);
  const [sessionsPageSize] = useState(10);
  const [sessionsLoading, setSessionsLoading] = useState(false);

  // 对话列表状态
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [traces, setTraces] = useState<TraceListItem[]>([]);
  const [tracesTotal, setTracesTotal] = useState(0);
  const [tracesPage, setTracesPage] = useState(1);
  const [tracesPageSize] = useState(10);
  const [tracesLoading, setTracesLoading] = useState(false);

  // 获取用户统计
  const fetchUserStats = useCallback(async () => {
    if (!userId) return;
    setUserLoading(true);
    try {
      const data = await tracingApi.getUserStats(userId, startDate, endDate, sourceId);
      setUserStats(data);
    } catch (error) {
      console.error("Failed to fetch user stats:", error);
    } finally {
      setUserLoading(false);
    }
  }, [userId, startDate, endDate, sourceId]);

  // 获取会话列表
  const fetchSessions = useCallback(async (page: number) => {
    if (!userId) return;
    setSessionsLoading(true);
    try {
      const data = await tracingApi.getSessions(page, sessionsPageSize, {
        user_id: userId,
        start_date: startDate,
        end_date: endDate,
        sourceId,
      });
      setSessions(data.items || []);
      setSessionsTotal(data.total || 0);
      // 默认选中第一个会话
      if (data.items && data.items.length > 0 && !selectedSessionId) {
        setSelectedSessionId(data.items[0].session_id);
      }
    } catch (error) {
      console.error("Failed to fetch sessions:", error);
    } finally {
      setSessionsLoading(false);
    }
  }, [userId, startDate, endDate, sourceId, sessionsPageSize, selectedSessionId]);

  // 获取对话列表
  const fetchTraces = useCallback(async (sessionId: string, page: number) => {
    if (!sessionId) return;
    setTracesLoading(true);
    try {
      const data = await tracingApi.getTraces(page, tracesPageSize, {
        session_id: sessionId,
        start_date: startDate,
        end_date: endDate,
        source_id: sourceId,
      });
      setTraces(data.items || []);
      setTracesTotal(data.total || 0);
    } catch (error) {
      console.error("Failed to fetch traces:", error);
    } finally {
      setTracesLoading(false);
    }
  }, [startDate, endDate, sourceId, tracesPageSize]);

  // Modal 打开时加载数据
  useEffect(() => {
    if (open && userId) {
      fetchUserStats();
      fetchSessions(1);
      setSessionsPage(1);
    }
  }, [open, userId, fetchUserStats, fetchSessions]);

  // 选中会话变化时加载对话
  useEffect(() => {
    if (selectedSessionId) {
      fetchTraces(selectedSessionId, 1);
      setTracesPage(1);
    }
  }, [selectedSessionId, fetchTraces]);

  // 关闭时重置状态
  const handleClose = () => {
    setUserStats(null);
    setSessions([]);
    setSessionsTotal(0);
    setSessionsPage(1);
    setSelectedSessionId(null);
    setTraces([]);
    setTracesTotal(0);
    setTracesPage(1);
    onClose();
  };

  // 会话分页变化
  const handleSessionsPageChange = (page: number) => {
    setSessionsPage(page);
    fetchSessions(page);
  };

  // 会话选中变化
  const handleSessionSelect = (sessionId: string) => {
    setSelectedSessionId(sessionId);
  };

  // 对话分页变化
  const handleTracesPageChange = (page: number) => {
    setTracesPage(page);
    if (selectedSessionId) {
      fetchTraces(selectedSessionId, page);
    }
  };

  return (
    <Modal
      title={
        <span>
          <User size={18} style={{ marginRight: 8 }} />
          用户详情
        </span>
      }
      open={open}
      onCancel={handleClose}
      width={800}
      footer={null}
      destroyOnClose
    >
      {userLoading ? (
        <div className={styles.loading}>
          <Spin />
        </div>
      ) : userStats ? (
        <div className={styles.modalContent}>
          {/* 顶部：用户统计 */}
          <div className={styles.topSection}>
            <UserStatsHeader userStats={userStats} />
          </div>

          {/* 下方：会话列表 + 对话流 */}
          <div className={styles.bottomSection}>
            <div className={styles.leftPanel}>
              <SessionCardList
                sessions={sessions}
                total={sessionsTotal}
                page={sessionsPage}
                pageSize={sessionsPageSize}
                loading={sessionsLoading}
                selectedSessionId={selectedSessionId}
                onSelect={handleSessionSelect}
                onPageChange={handleSessionsPageChange}
              />
            </div>
            <div className={styles.rightPanel}>
              <SessionTracesFlow
                traces={traces}
                total={tracesTotal}
                page={tracesPage}
                pageSize={tracesPageSize}
                loading={tracesLoading}
                onPageChange={handleTracesPageChange}
              />
            </div>
          </div>
        </div>
      ) : (
        <Empty />
      )}
    </Modal>
  );
}
```

- [ ] **Step 2: 创建 Modal 样式文件**

创建文件 `console/src/pages/Analytics/BusinessOverview/components/UserDetailModal/index.module.less`：

```less
.loading {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 300px;
}

.modalContent {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 70vh;
}

.topSection {
  flex-shrink: 0;
}

.bottomSection {
  display: flex;
  gap: 16px;
  flex: 1;
  min-height: 0;
}

.leftPanel {
  width: 280px;
  flex-shrink: 0;
  overflow-y: auto;
  border: 1px solid #f0f0f0;
  border-radius: 6px;
  padding: 12px;
}

.rightPanel {
  flex: 1;
  overflow-y: auto;
  border: 1px solid #f0f0f0;
  border-radius: 6px;
  padding: 12px;
}
```

- [ ] **Step 3: 提交**

```bash
git add console/src/pages/Analytics/BusinessOverview/components/UserDetailModal/
git commit -m "feat(business-overview): add UserDetailModal container component"
```

---

## Task 3: 创建 UserStatsHeader 组件

**Files:**
- Create: `console/src/pages/Analytics/BusinessOverview/components/UserDetailModal/UserStatsHeader.tsx`

- [ ] **Step 1: 创建用户统计头部组件**

创建文件 `console/src/pages/Analytics/BusinessOverview/components/UserDetailModal/UserStatsHeader.tsx`：

```tsx
import { Descriptions, Tag } from "antd";
import { useTranslation } from "react-i18next";
import { UserStats } from "../../../../../api/modules/tracing";

interface UserStatsHeaderProps {
  userStats: UserStats;
}

export default function UserStatsHeader({ userStats }: UserStatsHeaderProps) {
  const { t } = useTranslation();

  const formatTokens = (tokens: number) => {
    if (!tokens) return "0";
    if (tokens < 1000) return tokens.toString();
    if (tokens < 1000000) return `${(tokens / 1000).toFixed(1)}K`;
    return `${(tokens / 1000000).toFixed(2)}M`;
  };

  const formatDuration = (ms: number) => {
    if (!ms) return "-";
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${(ms / 60000).toFixed(1)}m`;
  };

  return (
    <div>
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

      {/* 模型使用 */}
      {userStats.model_usage.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <span style={{ fontWeight: 500, marginRight: 8 }}>模型使用:</span>
          {userStats.model_usage.map((m) => (
            <Tag key={m.model_name} style={{ marginBottom: 4 }}>
              {m.model_name}: {m.count} calls
            </Tag>
          ))}
        </div>
      )}

      {/* 工具使用 */}
      {userStats.tools_used.length > 0 && (
        <div style={{ marginTop: 8 }}>
          <span style={{ fontWeight: 500, marginRight: 8 }}>工具使用:</span>
          {userStats.tools_used.map((tool) => (
            <Tag
              key={tool.tool_name}
              color={tool.error_count > 0 ? "error" : "default"}
              style={{ marginBottom: 4 }}
            >
              {tool.tool_name}: {tool.count} calls
            </Tag>
          ))}
        </div>
      )}

      {/* 技能使用 */}
      {userStats.skills_used.length > 0 && (
        <div style={{ marginTop: 8 }}>
          <span style={{ fontWeight: 500, marginRight: 8 }}>技能使用:</span>
          {userStats.skills_used.map((s) => (
            <Tag key={s.skill_name} color="blue" style={{ marginBottom: 4 }}>
              {s.skill_name}: {s.count} calls
            </Tag>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: 提交**

```bash
git add console/src/pages/Analytics/BusinessOverview/components/UserDetailModal/UserStatsHeader.tsx
git commit -m "feat(business-overview): add UserStatsHeader component"
```

---

## Task 4: 创建 SessionCardList 组件

**Files:**
- Create: `console/src/pages/Analytics/BusinessOverview/components/UserDetailModal/SessionCardList.tsx`

- [ ] **Step 1: 创建会话卡片列表组件**

创建文件 `console/src/pages/Analytics/BusinessOverview/components/UserDetailModal/SessionCardList.tsx`：

```tsx
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
  const formatTokens = (tokens: number) => {
    if (!tokens) return "0";
    if (tokens < 1000) return tokens.toString();
    if (tokens < 1000000) return `${(tokens / 1000).toFixed(1)}K`;
    return `${(tokens / 1000000).toFixed(1)}M`;
  };

  const formatTime = (time: string | null) => {
    if (!time) return "-";
    return new Date(time).toLocaleString("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

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
```

- [ ] **Step 2: 在样式文件中添加会话列表样式**

在 `console/src/pages/Analytics/BusinessOverview/components/UserDetailModal/index.module.less` 末尾添加：

```less
// 会话列表
.sessionList {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.sessionListTitle {
  font-weight: 600;
  font-size: 14px;
  margin-bottom: 12px;
  color: #262626;
}

.sessionLoading {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 200px;
}

.sessionEmpty {
  text-align: center;
  color: #999;
  padding: 40px 0;
}

.sessionCard {
  padding: 12px;
  border: 1px solid #e8e8e8;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 8px;
  transition: all 0.2s;

  &:hover {
    border-color: #1890ff;
    background: #fafafa;
  }

  &.selected {
    border-color: #1890ff;
    background: #e6f7ff;
  }
}

.sessionId {
  font-family: monospace;
  font-size: 12px;
  color: #262626;
  margin-bottom: 6px;
  word-break: break-all;
}

.sessionMeta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #666;
  margin-bottom: 4px;
}

.sessionStats {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #999;
  margin-bottom: 4px;
}

.sessionTime {
  font-size: 11px;
  color: #999;
}

.sessionPagination {
  margin-top: 12px;
  text-align: center;
}
```

- [ ] **Step 3: 提交**

```bash
git add console/src/pages/Analytics/BusinessOverview/components/UserDetailModal/
git commit -m "feat(business-overview): add SessionCardList component"
```

---

## Task 5: 创建 SessionTracesFlow 组件

**Files:**
- Create: `console/src/pages/Analytics/BusinessOverview/components/UserDetailModal/SessionTracesFlow.tsx`

- [ ] **Step 1: 创建对话流组件**

创建文件 `console/src/pages/Analytics/BusinessOverview/components/UserDetailModal/SessionTracesFlow.tsx`：

```tsx
import { useState } from "react";
import { Timeline, Tag, Pagination, Spin, Empty } from "antd";
import { Clock, User, Bot, ChevronDown, ChevronUp } from "lucide-react";
import dayjs from "dayjs";
import { tracingApi, TraceListItem, TraceDetail } from "../../../../../api/modules/tracing";
import styles from "./index.module.less";

interface SessionTracesFlowProps {
  traces: TraceListItem[];
  total: number;
  page: number;
  pageSize: number;
  loading: boolean;
  onPageChange: (page: number) => void;
}

export default function SessionTracesFlow({
  traces,
  total,
  page,
  pageSize,
  loading,
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
        items={traces.map((trace) => {
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

                    {/* 工具调用 */}
                    {detail.tools_called.length > 0 && (
                      <div className={styles.toolsSection}>
                        <span className={styles.sectionLabel}>工具调用:</span>
                        {detail.tools_called.map((tool, idx) => (
                          <div key={idx} className={styles.toolCard}>
                            <div className={styles.toolName}>{tool.tool_name}</div>
                            {tool.duration_ms && (
                              <div className={styles.toolMeta}>
                                耗时: {formatDuration(tool.duration_ms)}
                              </div>
                            )}
                            {tool.error && (
                              <div className={styles.toolError}>
                                错误: {tool.error}
                              </div>
                            )}
                          </div>
                        ))}
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
```

- [ ] **Step 2: 在样式文件中添加对话流样式**

在 `console/src/pages/Analytics/BusinessOverview/components/UserDetailModal/index.module.less` 末尾添加：

```less
// 对话流
.tracesFlow {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.tracesTitle {
  font-weight: 600;
  font-size: 14px;
  margin-bottom: 12px;
  color: #262626;
}

.tracesLoading {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 200px;
}

.traceItem {
  padding-bottom: 8px;
}

.traceHeader {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.traceTime {
  font-size: 12px;
  color: #666;
}

.traceDuration {
  font-size: 12px;
  color: #999;
  margin-left: auto;
}

.traceMeta {
  display: flex;
  align-items: center;
  font-size: 12px;
  color: #666;
  margin-bottom: 6px;
}

.traceModel {
  margin-left: 8px;
  color: #1890ff;
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.traceExpandBtn {
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  color: #1890ff;
  font-size: 12px;
  margin-top: 4px;

  &:hover {
    color: #40a9ff;
  }
}

.traceDetail {
  margin-top: 12px;
  padding: 12px;
  background: #fafafa;
  border-radius: 6px;
}

.userMessage {
  background: #f5f5f5;
  padding: 12px;
  border-radius: 6px;
  margin-bottom: 8px;
}

.modelOutput {
  background: #e6f7ff;
  padding: 12px;
  border-radius: 6px;
  margin-bottom: 8px;
}

.messageLabel {
  font-weight: 500;
  font-size: 12px;
  color: #666;
  margin-bottom: 6px;
  display: flex;
  align-items: center;
}

.messageContent {
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.skillsSection {
  margin: 8px 0;
}

.sectionLabel {
  font-size: 12px;
  color: #666;
  margin-right: 8px;
}

.tagList {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 4px;
}

.toolsSection {
  margin: 8px 0;
}

.toolCard {
  background: #fff;
  padding: 8px 12px;
  border-radius: 4px;
  margin: 4px 0;
  border: 1px solid #e8e8e8;
}

.toolName {
  font-weight: 500;
  font-size: 12px;
  color: #262626;
}

.toolMeta {
  font-size: 11px;
  color: #999;
  margin-top: 4px;
}

.toolError {
  font-size: 11px;
  color: #ff4d4f;
  margin-top: 4px;
}

.errorSection {
  margin: 8px 0;
}

.errorText {
  background: #fff1f0;
  padding: 8px;
  border-radius: 4px;
  font-size: 11px;
  color: #ff4d4f;
  margin: 4px 0 0 0;
  white-space: pre-wrap;
  word-break: break-word;
}

.tracesPagination {
  margin-top: 12px;
  text-align: center;
}
```

- [ ] **Step 3: 提交**

```bash
git add console/src/pages/Analytics/BusinessOverview/components/UserDetailModal/
git commit -m "feat(business-overview): add SessionTracesFlow component with expandable details"
```

---

## Task 6: 集成到运营看板主页面

**Files:**
- Modify: `console/src/pages/Analytics/BusinessOverview/index.tsx`
- Modify: `console/src/pages/Analytics/BusinessOverview/index.module.less`

- [ ] **Step 1: 在运营看板主页面引入 UserDetailModal**

在 `console/src/pages/Analytics/BusinessOverview/index.tsx` 中添加导入和状态：

```tsx
// 在文件顶部 import 区域添加
import UserDetailModal from "./components/UserDetailModal";

// 在组件内部，state 定义区域添加
const [modalOpen, setModalOpen] = useState(false);
const [selectedUserId, setSelectedUserId] = useState<string | null>(null);
```

- [ ] **Step 2: 修改 renderUserList 函数添加点击事件**

修改 `console/src/pages/Analytics/BusinessOverview/index.tsx` 中的 `renderUserList` 函数，在 userItem div 上添加 onClick：

```tsx
// 找到 renderUserList 函数，修改 userItem div
{users.map((user, index) => (
  <div
    key={user.userId}
    className={styles.userItem}
    onClick={() => {
      setSelectedUserId(user.userId);
      setModalOpen(true);
    }}
    style={{ cursor: "pointer" }}
  >
    {/* 保持原有内容不变 */}
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
```

- [ ] **Step 3: 在组件末尾添加 UserDetailModal**

在 `console/src/pages/Analytics/BusinessOverview/index.tsx` 的 return 语句末尾，`</div>` 之前添加：

```tsx
      {/* 用户详情弹窗 */}
      <UserDetailModal
        open={modalOpen}
        userId={selectedUserId}
        startDate={startDate.format("YYYY-MM-DD")}
        endDate={calculatedEndDate.format("YYYY-MM-DD")}
        sourceId={platform !== "all" ? platform : undefined}
        onClose={() => {
          setModalOpen(false);
          setSelectedUserId(null);
        }}
      />
    </div>
  );
}
```

- [ ] **Step 4: 添加用户行悬浮样式**

在 `console/src/pages/Analytics/BusinessOverview/index.module.less` 中找到 `.userItem` 样式，添加悬浮效果：

```less
.userItem {
  display: flex;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid #f0f0f0;
  cursor: pointer;
  transition: background 0.2s;

  &:hover {
    background: #f5f5f5;
  }

  &:last-child {
    border-bottom: none;
  }
}
```

- [ ] **Step 5: 提交**

```bash
git add console/src/pages/Analytics/BusinessOverview/
git commit -m "feat(business-overview): integrate UserDetailModal into hot users list"
```

---

## Task 7: 添加国际化文案

**Files:**
- Modify: `console/src/locales/zh.json`
- Modify: `console/src/locales/en.json`

- [ ] **Step 1: 添加中文文案**

在 `console/src/locales/zh.json` 的 `analytics` 命名空间中添加：

```json
{
  "analytics": {
    "userDetail": "用户详情",
    "sessionList": "会话列表",
    "tracesFlow": "对话流",
    "viewDetail": "查看详情",
    "collapseDetail": "收起详情",
    "userInput": "用户输入",
    "modelOutput": "模型输出",
    "toolsCalled": "工具调用",
    "noSessionData": "暂无会话数据",
    "noTraceData": "暂无对话数据"
  }
}
```

- [ ] **Step 2: 添加英文文案**

在 `console/src/locales/en.json` 的 `analytics` 命名空间中添加：

```json
{
  "analytics": {
    "userDetail": "User Details",
    "sessionList": "Sessions",
    "tracesFlow": "Conversation Flow",
    "viewDetail": "View Details",
    "collapseDetail": "Collapse",
    "userInput": "User Input",
    "modelOutput": "Model Output",
    "toolsCalled": "Tools Called",
    "noSessionData": "No session data",
    "noTraceData": "No conversation data"
  }
}
```

- [ ] **Step 3: 提交**

```bash
git add console/src/locales/
git commit -m "feat(business-overview): add i18n for UserDetailModal"
```

---

## Task 8: 构建验证

**Files:**
- 无文件修改，仅验证

- [ ] **Step 1: 运行前端类型检查**

```bash
cd console && npm run type-check
```

预期：无类型错误

- [ ] **Step 2: 运行前端构建**

```bash
cd console && npm run build
```

预期：构建成功，无错误

- [ ] **Step 3: 最终提交**

```bash
git add -A
git commit -m "feat(business-overview): add user detail modal with session list and traces flow"
```

---

## 验收清单

- [ ] 点击热门用户表格行，Modal 正确打开
- [ ] 用户统计信息正确展示（会话数、对话数、Token、模型/工具/技能使用）
- [ ] 会话列表正确加载，支持分页
- [ ] 点击会话卡片切换选中状态，右侧加载该会话的对话列表
- [ ] 对话流正确展示对话列表（基础信息：时间、Token、状态、模型、技能数）
- [ ] 点击对话展开显示用户输入和模型输出
- [ ] 技能使用数量在列表中正确显示，详情中展示技能名称列表
- [ ] 工具调用数量在列表中正确显示，详情中展示工具调用卡片（名称、耗时、错误）
- [ ] 关闭 Modal 后状态正确重置
