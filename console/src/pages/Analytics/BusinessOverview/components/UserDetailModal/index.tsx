import { useState, useEffect, useCallback } from "react";
import { Modal, Spin, Empty, message } from "antd";
import { User } from "lucide-react";
import {
  tracingApi,
  UserStats,
  SessionStats,
  SessionListItem,
  TraceListItem,
} from "../../../../../api/modules/tracing";
import { UserDetailModalProps } from "../../types";
import UserStatsHeader from "./UserStatsHeader";
import SessionCardList from "./SessionCardList";
import ReadOnlySessionChat from "./ReadOnlySessionChat";
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

  // 会话统计状态
  const [sessionStats, setSessionStats] = useState<SessionStats | null>(null);
  const [statsCollapsed, setStatsCollapsed] = useState(false);

  // 会话列表状态
  const [sessions, setSessions] = useState<SessionListItem[]>([]);
  const [sessionsTotal, setSessionsTotal] = useState(0);
  const [sessionsPage, setSessionsPage] = useState(1);
  const [sessionsPageSize] = useState(10);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [sessionsCollapsed, setSessionsCollapsed] = useState(false);
  const [hasAutoSelectedSession, setHasAutoSelectedSession] = useState(false);

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
      message.error("获取用户统计失败");
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
        source_id: sourceId,
      });
      setSessions(data.items || []);
      setSessionsTotal(data.total || 0);
    } catch (error) {
      console.error("Failed to fetch sessions:", error);
      message.error("获取会话列表失败");
    } finally {
      setSessionsLoading(false);
    }
  }, [userId, startDate, endDate, sourceId, sessionsPageSize]);

  // 获取会话统计
  const fetchSessionStats = useCallback(async (sessionId: string) => {
    try {
      const data = await tracingApi.getSessionStats(
        sessionId,
        startDate,
        endDate,
        sourceId,
      );
      setSessionStats(data);
    } catch (error) {
      console.error("Failed to fetch session stats:", error);
      message.error("获取会话统计失败");
    }
  }, [startDate, endDate, sourceId]);

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
      message.error("获取对话列表失败");
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
      setHasAutoSelectedSession(false);
    }
  }, [open, userId, fetchUserStats, fetchSessions]);

  // 首次打开详情弹窗时自动选中第一条会话，便于直接查看聊天内容
  useEffect(() => {
    if (
      !open ||
      hasAutoSelectedSession ||
      selectedSessionId ||
      sessions.length === 0
    ) {
      return;
    }

    const firstSessionId = sessions[0].session_id;
    setHasAutoSelectedSession(true);
    setSelectedSessionId(firstSessionId);
    fetchSessionStats(firstSessionId);
  }, [
    open,
    hasAutoSelectedSession,
    selectedSessionId,
    sessions,
    fetchSessionStats,
  ]);

  // 选中会话变化时加载对话
  useEffect(() => {
    if (selectedSessionId) {
      fetchTraces(selectedSessionId, 1);
      setTracesPage(1);
    } else {
      setTraces([]);
      setTracesTotal(0);
    }
  }, [selectedSessionId, fetchTraces]);

  // 关闭时重置状态
  const handleClose = () => {
    setUserStats(null);
    setSessionStats(null);
    setStatsCollapsed(false);
    setSessions([]);
    setSessionsTotal(0);
    setSessionsPage(1);
    setSessionsCollapsed(false);
    setHasAutoSelectedSession(false);
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

  // 会话选中变化 - 点击已选中的会话则取消选中
  const handleSessionSelect = (sessionId: string) => {
    if (selectedSessionId === sessionId) {
      // 取消选中
      setSelectedSessionId(null);
      setSessionStats(null);
    } else {
      // 选中新会话
      setSelectedSessionId(sessionId);
      fetchSessionStats(sessionId);
    }
  };

  // 对话分页变化
  const handleTracesPageChange = (page: number) => {
    setTracesPage(page);
    if (selectedSessionId) {
      fetchTraces(selectedSessionId, page);
    }
  };

  // 判断当前显示的是用户级还是会话级统计
  const showSessionStats = selectedSessionId !== null && sessionStats !== null;

  return (
    <Modal
      title={
        <div className={styles.modalTitleBlock}>
          <span className={styles.modalTitleIcon}>
            <User size={18} />
          </span>
          <div className={styles.modalTitleText}>
            <div className={styles.modalTitle}>用户详情</div>
            <div className={styles.modalSubtitle}>
              调用排行 · 运营看板 · 只读审计视图
            </div>
          </div>
        </div>
      }
      open={open}
      onCancel={handleClose}
      width="100vw"
      footer={null}
      destroyOnClose
      className={styles.userDetailModal}
      classNames={{ body: styles.userDetailModalBody }}
      style={{ top: 0, paddingBottom: 0 }}
    >
      {userLoading ? (
        <div className={styles.loading}>
          <Spin />
        </div>
      ) : userStats ? (
        <div className={styles.modalContent}>
          {/* 顶部：统计信息 */}
          <div className={styles.topSection}>
            <UserStatsHeader
              userStats={userStats}
              sessionStats={showSessionStats ? sessionStats : null}
              collapsed={statsCollapsed}
              onToggleCollapsed={() => setStatsCollapsed((value) => !value)}
            />
          </div>

          {/* 下方：会话列表 + 对话流 */}
          <div className={styles.bottomSection}>
            <div
              className={`${styles.leftPanel} ${
                sessionsCollapsed ? styles.leftPanelCollapsed : ""
              }`}
            >
              <SessionCardList
                sessions={sessions}
                total={sessionsTotal}
                page={sessionsPage}
                pageSize={sessionsPageSize}
                loading={sessionsLoading}
                selectedSessionId={selectedSessionId}
                collapsed={sessionsCollapsed}
                onSelect={handleSessionSelect}
                onPageChange={handleSessionsPageChange}
                onToggleCollapsed={() =>
                  setSessionsCollapsed((value) => !value)
                }
              />
            </div>
            <div className={styles.rightPanel}>
              <ReadOnlySessionChat
                selectedSessionId={selectedSessionId}
                userId={userId}
                traces={traces}
                total={tracesTotal}
                page={tracesPage}
                pageSize={tracesPageSize}
                tracesLoading={tracesLoading}
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
