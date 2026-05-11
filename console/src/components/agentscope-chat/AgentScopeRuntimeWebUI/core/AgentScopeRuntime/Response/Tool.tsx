import React from "react";
import {
  AgentScopeRuntimeRunStatus,
  IAgentScopeRuntimeMessage,
  IDataContent,
} from "../types";
import { ToolCall } from "@/components/agentscope-chat";
import { useChatAnywhereOptions } from "../../Context/ChatAnywhereOptionsContext";
import Approval from "./Approval";
import { buildToolTitle, getToolDisplayName } from "./ToolTitle";

const HIDDEN_TOOL_NAMES = new Set(["update_task_progress"]);

const Tool = React.memo(function ({
  data,
  isApproval = false,
}: {
  data: IAgentScopeRuntimeMessage;
  isApproval?: boolean;
}) {
  const customToolRenderConfig =
    useChatAnywhereOptions((v) => v.customToolRenderConfig) || {};

  if (!data.content?.length) return null;
  const content = data.content as IDataContent<{
    name: string;
    server_label?: string;
    arguments: Record<string, any>;
    output: Record<string, any>;
    summary?: string;
    output_summary?: string;
  }>[];
  const loading = data.status === AgentScopeRuntimeRunStatus.InProgress;
  const toolName = content[0].data.name;
  if (HIDDEN_TOOL_NAMES.has(toolName)) return null;

  const serverLabel = content[0].data.server_label;
  const defaultTitle = getToolDisplayName(toolName, serverLabel);
  const input = content[0]?.data?.arguments;
  const summary = content[0]?.data?.summary;
  const output = content[1]?.data?.output;
  const outputSummary = content[1]?.data?.output_summary;
  const title = buildToolTitle({
    loading,
    toolName,
    defaultTitle,
    input,
    summary,
  });

  let node;

  if (customToolRenderConfig[toolName]) {
    const C = customToolRenderConfig[toolName];
    node = <C data={data} />;
  } else {
    node = (
      <ToolCall
        loading={loading}
        msgStatus={data.status}
        defaultOpen={false}
        title={title}
        input={input}
        output={output}
        outputSummary={outputSummary}
      ></ToolCall>
    );
  }

  return (
    <>
      {node}
      {isApproval && <Approval data={data} />}
    </>
  );
});

export default Tool;
