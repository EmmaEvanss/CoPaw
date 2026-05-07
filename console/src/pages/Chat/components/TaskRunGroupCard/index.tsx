import { Fragment, useState } from "react";
import type { IAgentScopeRuntimeWebUIMessage } from "@/components/agentscope-chat/AgentScopeRuntimeWebUI/core/types/IMessages";
import type {
  ChatApprovalActionCardData,
  ChatRuntimeRequestCardData,
  ChatRuntimeResponseCardData,
  ChatTaskRunGroupCardData,
} from "../../messageMeta";
import { formatMessageTime } from "../../messageMeta";
import ApprovalActionCard from "../ApprovalActionCard";
import RuntimeRequestCard from "../RuntimeRequestCard";
import RuntimeResponseCard from "../RuntimeResponseCard";

function NestedTaskRunMessages(props: {
  messages: IAgentScopeRuntimeWebUIMessage[];
}) {
  return (
    <>
      {props.messages.map((message, messageIndex) => (
        <Fragment key={message.id}>
          {(message.cards || []).map((card, cardIndex) => {
            const key = `${message.id}-${card.id || card.code}-${cardIndex}`;
            if (card.code === "AgentScopeRuntimeRequestCard") {
              return (
                <RuntimeRequestCard
                  key={key}
                  data={card.data as ChatRuntimeRequestCardData}
                />
              );
            }
            if (card.code === "AgentScopeRuntimeResponseCard") {
              return (
                <RuntimeResponseCard
                  key={key}
                  data={card.data as ChatRuntimeResponseCardData}
                  isLast={
                    messageIndex === props.messages.length - 1
                    && cardIndex === (message.cards || []).length - 1
                  }
                />
              );
            }
            if (card.code === "ApprovalAction") {
              return (
                <ApprovalActionCard
                  key={key}
                  data={card.data as ChatApprovalActionCardData}
                />
              );
            }
            return null;
          })}
        </Fragment>
      ))}
    </>
  );
}

export default function TaskRunGroupCard(props: {
  data: ChatTaskRunGroupCardData;
}) {
  const { data } = props;
  const [expanded, setExpanded] = useState(false);
  const hasSteps = data.stepMessages.length > 0;
  const taskName = data.taskName || `任务 ${data.runIndex + 1}`;
  const headerText = data.headerMeta?.timestamp
    ? `${taskName}，执行时间：${formatMessageTime(data.headerMeta.timestamp)}，结果如下`
    : `${taskName}，结果如下`;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 12,
        width: "100%",
        boxSizing: "border-box",
      }}
    >
      <div
        data-testid="task-run-divider"
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          width: "100%",
          color: "rgba(0, 0, 0, 0.45)",
          fontSize: 12,
          boxSizing: "border-box",
        }}
      >
        <div
          style={{ flex: 1, borderTop: "1px solid rgba(0, 0, 0, 0.12)" }}
        />
        <span style={{ textAlign: "center", whiteSpace: "nowrap", fontWeight: "bold"}}>
          {headerText}
        </span>
        <div
          style={{ flex: 1, borderTop: "1px solid rgba(0, 0, 0, 0.12)" }}
        />
      </div>
      <NestedTaskRunMessages messages={data.finalMessages} />
      {hasSteps && (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <button
            type="button"
            data-testid="task-run-toggle"
            onClick={() => setExpanded((prev) => !prev)}
            style={{
              alignSelf: "flex-start",
              border: "none",
              background: "transparent",
              padding: 0,
              color: "#1677ff",
              cursor: "pointer",
            }}
          >
            {expanded ? "收起步骤" : "查看步骤"}
          </button>
          {expanded && (
            <div
              data-testid="task-run-steps"
              style={{
                borderLeft: "2px solid rgba(22, 119, 255, 0.18)",
                paddingLeft: 16,
              }}
            >
              <NestedTaskRunMessages messages={data.stepMessages} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
