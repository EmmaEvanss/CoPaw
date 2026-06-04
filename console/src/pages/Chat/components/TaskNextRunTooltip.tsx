import React from "react";
import { Tooltip } from "antd";
import { createGlobalStyle } from "antd-style";

const Style = createGlobalStyle`
.chat-task-next-run-tooltip .ant-tooltip-inner {
  min-width: 156px;
  padding: 8px 10px;
  border-radius: 6px;
  background: rgba(29, 33, 46, 0.96);
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.18);
}

.chat-task-next-run-tooltip-title {
  margin-bottom: 6px;
  color: rgba(255, 255, 255, 0.72);
  font-size: 12px;
  line-height: 16px;
  font-weight: 500;
}

.chat-task-next-run-tooltip-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.chat-task-next-run-tooltip-row {
  display: flex;
  align-items: center;
  gap: 7px;
  color: #ffffff;
  font-size: 12px;
  line-height: 16px;
  white-space: nowrap;
}

.chat-task-next-run-tooltip-index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 4px;
  background: rgba(91, 138, 255, 0.20);
  color: #c9d7ff;
  font-size: 10px;
  line-height: 16px;
  font-weight: 600;
}
`;

function TooltipContent({ runTimes }: { runTimes: string[] }) {
  return (
    <div>
      <div className="chat-task-next-run-tooltip-title">之后三次运行时间</div>
      <div className="chat-task-next-run-tooltip-list">
        {runTimes.map((runTime, index) => (
          <div
            className="chat-task-next-run-tooltip-row"
            key={`${runTime}-${index}`}
          >
            <span className="chat-task-next-run-tooltip-index">
              {index + 1}
            </span>
            <span>{runTime}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function TaskNextRunTooltip({
  runTimes,
  children,
}: {
  runTimes: string[];
  children: React.ReactElement;
}) {
  if (runTimes.length === 0) {
    return children;
  }

  return (
    <>
      <Style />
      <Tooltip
        classNames={{ root: "chat-task-next-run-tooltip" }}
        placement="topLeft"
        title={<TooltipContent runTimes={runTimes} />}
      >
        {children}
      </Tooltip>
    </>
  );
}
