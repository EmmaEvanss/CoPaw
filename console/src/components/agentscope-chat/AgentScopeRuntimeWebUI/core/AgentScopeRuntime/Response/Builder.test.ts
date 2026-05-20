import { describe, expect, it } from "vitest";
import { mergeToolMessages } from "./ToolMessageMerge";
import {
  AgentScopeRuntimeContentType,
  type IDataContent,
  AgentScopeRuntimeMessageType,
  AgentScopeRuntimeRunStatus,
} from "../types";

describe("AgentScopeRuntimeResponseBuilder tool merge", () => {
  it("merges MCP tool calls using tool_name and tool_call_id aliases", () => {
    const messages = mergeToolMessages([
      {
        id: "call-message",
        object: "message",
        role: "assistant",
        type: AgentScopeRuntimeMessageType.MCP_CALL,
        status: AgentScopeRuntimeRunStatus.Completed,
        content: [
          {
            type: AgentScopeRuntimeContentType.DATA,
            status: AgentScopeRuntimeRunStatus.Completed,
            data: {
              tool_call_id: "mcp-call-1",
              tool_name: "fetch_customer_profile",
              arguments: "{}",
            },
          },
        ],
      },
      {
        id: "output-message",
        object: "message",
        role: "tool",
        type: AgentScopeRuntimeMessageType.MCP_CALL_OUTPUT,
        status: AgentScopeRuntimeRunStatus.Completed,
        content: [
          {
            type: AgentScopeRuntimeContentType.DATA,
            status: AgentScopeRuntimeRunStatus.Completed,
            data: {
              tool_call_id: "mcp-call-1",
              tool_name: "fetch_customer_profile",
              output: "[]",
            },
          },
        ],
      },
    ]);

    expect(messages).toHaveLength(1);
    expect(messages[0].content).toHaveLength(2);
    expect((messages[0].content[0] as IDataContent).data.tool_name).toBe(
      "fetch_customer_profile",
    );
    expect((messages[0].content[1] as IDataContent).data.output).toBe("[]");
  });

  it("keeps unmatched MCP output messages visible", () => {
    const messages = mergeToolMessages([
      {
        id: "output-message",
        object: "message",
        role: "tool",
        type: AgentScopeRuntimeMessageType.MCP_CALL_OUTPUT,
        status: AgentScopeRuntimeRunStatus.Completed,
        content: [
          {
            type: AgentScopeRuntimeContentType.DATA,
            status: AgentScopeRuntimeRunStatus.Completed,
            data: {
              tool_name: "fetch_customer_profile",
              output: "[]",
            },
          },
        ],
      },
    ]);

    expect(messages).toHaveLength(1);
    expect((messages[0].content[0] as IDataContent).data.tool_name).toBe(
      "fetch_customer_profile",
    );
  });
});
