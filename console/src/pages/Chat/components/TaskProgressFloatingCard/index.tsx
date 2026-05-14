import { useState, useEffect } from "react";
import {
  SparkLoadingLine,
  SparkCheckCircleLine,
  SparkProjectNoLine,
  SparkDownLine,
} from "@agentscope-ai/icons";
import type { ChatTaskProgressData } from "../../taskProgressEvents";
import { emitTaskProgressUpdate } from "../../taskProgressEvents";
import Style from "./style";

export default function TaskProgressFloatingCard(props: {
  progress: ChatTaskProgressData | null;
}) {
  const { progress } = props;
  const [collapsed, setCollapsed] = useState(true);

  // 新 turn 出现时重置为折叠状态
  useEffect(() => {
    if (progress) {
      setCollapsed(true);
    }
  }, [progress?.turn_id]);

  useEffect(() => {
    if (!progress) return;
    if (progress.phase_status === "completed") {
      const timer = setTimeout(() => emitTaskProgressUpdate(null), 1500);
      return () => clearTimeout(timer);
    }
    if (progress.phase_status === "cancelled") {
      const timer = setTimeout(() => emitTaskProgressUpdate(null), 800);
      return () => clearTimeout(timer);
    }
  }, [progress?.turn_id, progress?.phase_status]);

  if (!progress) return null;

  // 完成态
  if (progress.phase_status === "completed") {
    return (
      <>
        <Style />
        <div className="task-progress-floating--completed">
          <SparkCheckCircleLine style={{ fontSize: 16 }} />
          所有步骤已完成
        </div>
      </>
    );
  }

  // 取消态
  if (progress.phase_status === "cancelled") {
    return (
      <>
        <Style />
        <div className="task-progress-floating--cancelled">
          <SparkProjectNoLine style={{ fontSize: 16 }} />
          任务已取消
        </div>
      </>
    );
  }

  // active 态
  const currentIndex = progress.current_step_index ?? 0;
  const progressPct = progress.total_steps > 0
    ? `${(currentIndex / progress.total_steps) * 100}%`
    : "0%";

  return (
    <>
      <Style />
      <div className="task-progress-floating">
        {/* 进度条 */}
        <div className="task-progress-floating-progress-bar">
          <div
            className="task-progress-floating-progress-bar-fill"
            style={{ width: progressPct }}
          />
        </div>

        {/* 标题栏 */}
        <div
          className="task-progress-floating-header"
          role="button"
          tabIndex={0}
          onClick={() => setCollapsed(!collapsed)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              setCollapsed((prev) => !prev);
            }
          }}
        >
          <SparkProjectNoLine className="task-progress-floating-header-icon" />
          <span className="task-progress-floating-header-title">
            {collapsed
              ? (progress.items.find((i) => i.status === "running")?.label
                  || progress.title
                  || "任务计划")
              : (progress.title || "任务计划")}
          </span>
          <span className="task-progress-floating-header-badge">
            {progress.current_step_index != null
              ? `${progress.current_step_index}/${progress.total_steps}`
              : progress.total_steps}
          </span>
          <span
            className={`task-progress-floating-header-arrow${
              collapsed ? " task-progress-floating-header-arrow--collapsed" : ""
            }`}
          >
            <SparkDownLine />
          </span>
        </div>

        {/* 步骤列表 */}
        {!collapsed && (
          <>
            <div className="task-progress-floating-divider" />
            <div className="task-progress-floating-list">
              {progress.items.map((item) => (
                <div
                  key={item.id || item.label}
                  className={`task-progress-floating-item${
                    item.status === "running"
                      ? " task-progress-floating-item--running"
                      : ""
                  }`}
                >
                  <span className="task-progress-floating-item-icon">
                    {item.status === "running" ? (
                      <SparkLoadingLine
                        className="task-progress-floating-item-icon--spin"
                        spin
                      />
                    ) : item.status === "done" ? (
                      <SparkCheckCircleLine className="task-progress-floating-item-icon--done" />
                    ) : (
                      <span className="task-progress-floating-item-icon--todo" />
                    )}
                  </span>
                  <span
                    className={`task-progress-floating-item-label task-progress-floating-item-label--${item.status}`}
                  >
                    {item.label}
                  </span>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </>
  );
}
