import { useState, useEffect, useCallback } from "react";
import { Modal, Spin, Empty, message } from "antd";
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
      // 默认选中第一个会话
      if (data.items && data.items.length > 0 && !selectedSessionId) {
        setSelectedSessionId(data.items[0].session_id);
      }
    } catch (error) {
      console.error("Failed to fetch sessions:", error);
      message.error("获取会话列表失败");
    } finally {
      setSessionsLoading(false);
    }
  }, [userId, startDate, endDate, sourceId, sessionsPageSize]);

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
