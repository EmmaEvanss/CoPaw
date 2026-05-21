import { describe, expect, it } from "vitest";
import {
  buildToolTitle,
  getToolDisplayName,
  resolveServerLabel,
  resolveToolName,
} from "./ToolTitle";

describe("tool call title", () => {
  it("keeps a clean backend summary with the concrete object", () => {
    const title = buildToolTitle({
      loading: true,
      toolName: "read_file",
      defaultTitle: getToolDisplayName("read_file"),
      input: '{"file_path": "/tmp/demo.txt"}',
      summary: "正在读取 demo.txt",
    });

    expect(title).toBe("正在读取 demo.txt");
  });

  it("extracts the basename for file-read arguments when summary is unsafe", () => {
    const title = buildToolTitle({
      loading: false,
      toolName: "read_file",
      defaultTitle: getToolDisplayName("read_file"),
      input: '{"file_path": "/workspace/reports/demo.txt", "limit": 2000}',
      summary:
        '正在工具操作：{"file_path": "/workspace/reports/demo.txt", "limit": 2000}',
    });

    expect(title).toBe("读取文件：demo.txt");
    expect(title).not.toContain("file_path");
    expect(title).not.toContain("limit");
  });

  it("shows the glob pattern without exposing the whole JSON payload", () => {
    const title = buildToolTitle({
      loading: true,
      toolName: "glob_search",
      defaultTitle: getToolDisplayName("glob_search"),
      input: '{"pattern": "src/**/*.tsx", "root": "/workspace"}',
      summary: '{"pattern": "src/**/*.tsx", "root": "/workspace"}',
    });

    expect(title).toBe("正在查找文件：src/**/*.tsx");
    expect(title).not.toContain("root");
  });

  it("falls back to the tool label when there is no safe object hint", () => {
    const title = buildToolTitle({
      loading: false,
      toolName: "execute_shell_command",
      defaultTitle: getToolDisplayName("execute_shell_command"),
      input: '{"command": "cat /etc/passwd"}',
      summary: '{"command": "cat /etc/passwd"}',
    });

    expect(title).toBe("调用工具：执行操作");
    expect(title).not.toContain("cat");
  });

  it("keeps unknown tool names visible while hiding opaque business params", () => {
    const title = buildToolTitle({
      loading: true,
      toolName: "query_business_opportunity",
      defaultTitle: getToolDisplayName("query_business_opportunity"),
      input: '{"bbkOrgId": "V00", "brnOrgId": "V00001"}',
      summary: '{"bbkOrgId": "V00", "brnOrgId": "V00001"}',
    });

    expect(title).toBe("正在调用：query_business_opportunity");
    expect(title).not.toContain("bbkOrgId");
    expect(title).not.toContain("V00001");
  });

  it("does not use vague browser summaries as the visible title", () => {
    const title = buildToolTitle({
      loading: true,
      toolName: "browser_use",
      defaultTitle: getToolDisplayName("browser_use"),
      input: '{"action": "type", "text": "chengdu"}',
      summary: "正在 chengdu",
    });

    expect(title).toBe("正在网页操作：chengdu");
  });

  it("keeps the browser action label for URL path hints", () => {
    const title = buildToolTitle({
      loading: true,
      toolName: "browser_use",
      defaultTitle: getToolDisplayName("browser_use"),
      input:
        '{"action": "open", "url": "https://weather.com.cn/weather/101270101.shtml"}',
      summary: "正在 101270101.shtml",
    });

    expect(title).toBe("正在网页操作：weather.com.cn/weather/101270101.shtml");
  });

  it("resolves MCP tool aliases instead of falling back to generic labels", () => {
    const data = {
      tool_name: "fetch_customer_profile",
      mcp_server: "crm",
    };

    expect(resolveToolName(data)).toBe("fetch_customer_profile");
    expect(resolveServerLabel(data)).toBe("crm");
    expect(
      getToolDisplayName(resolveToolName(data), resolveServerLabel(data)),
    ).toBe("[crm] fetch_customer_profile");
  });

  it("ignores generic summaries and shows the resolved MCP tool name", () => {
    const data = {
      tool: {
        name: "search_customer_cases",
      },
    };
    const toolName = resolveToolName(data);
    const title = buildToolTitle({
      loading: true,
      toolName,
      defaultTitle: getToolDisplayName(toolName),
      input: "{}",
      summary: "正在工具操作",
    });

    expect(toolName).toBe("search_customer_cases");
    expect(title).toBe("正在调用：search_customer_cases");
  });
});
