/**
 * 我的 MCP 管理 API
 */
import { request } from "../request";
import { mergeHeaders } from "../mergeHeaders";
import type {
  MyMCPListItem,
  MyMCPDetail,
  MyMCPCreateRequest,
  MyMCPDraftTestRequest,
  MyMCPUpdateRequest,
  PublishMCPRequest,
  PublishMCPResponse,
  PublishSingleMCPRequest,
  PublishSingleMCPResponse,
  MCPTestResult,
} from "../types";

export const myMcpApi = {
  /**
   * 获取我的 MCP 列表
   */
  listMyMCP: async (): Promise<MyMCPListItem[]> => {
    return request<MyMCPListItem[]>("/market/my-mcp");
  },

  /**
   * 获取单个 MCP 详情
   */
  getMyMCPDetail: async (clientKey: string): Promise<MyMCPDetail> => {
    return request<MyMCPDetail>(`/market/my-mcp/${encodeURIComponent(clientKey)}`);
  },

  /**
   * 创建新的 MCP
   */
  createMyMCP: async (data: MyMCPCreateRequest): Promise<MyMCPDetail> => {
    return request<MyMCPDetail>("/market/my-mcp", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  /**
   * 更新 MCP 配置
   */
  updateMyMCP: async (
    clientKey: string,
    data: MyMCPUpdateRequest
  ): Promise<MyMCPDetail> => {
    return request<MyMCPDetail>(`/market/my-mcp/${encodeURIComponent(clientKey)}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },

  /**
   * 删除 MCP
   */
  deleteMyMCP: async (clientKey: string): Promise<{ message: string }> => {
    return request<{ message: string }>(
      `/market/my-mcp/${encodeURIComponent(clientKey)}`,
      { method: "DELETE" }
    );
  },

  /**
   * 启用/禁用 MCP
   */
  toggleMyMCP: async (clientKey: string): Promise<MyMCPDetail> => {
    return request<MyMCPDetail>(
      `/market/my-mcp/${encodeURIComponent(clientKey)}/toggle`,
      { method: "PATCH" }
    );
  },

  /**
   * 测试 MCP 连接
   */
  testMyMCPConnection: async (clientKey: string): Promise<MCPTestResult> => {
    return request<MCPTestResult>(
      `/market/my-mcp/${encodeURIComponent(clientKey)}/test`,
      { method: "POST" }
    );
  },

  /**
   * 测试草稿 MCP 连接
   */
  testMyMCPDraftConnection: async (
    data: MyMCPDraftTestRequest
  ): Promise<MCPTestResult> => {
    return request<MCPTestResult>("/market/my-mcp/draft-test", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  /**
   * 发布 MCP 到市场（管理员）
   */
  publishToMarket: async (
    data: PublishMCPRequest
  ): Promise<PublishMCPResponse> => {
    const opts: RequestInit = {
      method: "POST",
      ...(mergeHeaders({
        "Content-Type": "application/json",
        "X-Manager": "true",
      })),
      body: JSON.stringify(data),
    };
    return request<PublishMCPResponse>("/market/my-mcp/publish", opts);
  },

  /**
   * 发布单个 MCP 到市场（管理员）
   */
  publishSingleToMarket: async (
    clientKey: string,
    data: PublishSingleMCPRequest
  ): Promise<PublishSingleMCPResponse> => {
    const opts: RequestInit = {
      method: "POST",
      ...(mergeHeaders({
        "Content-Type": "application/json",
        "X-Manager": "true",
      })),
      body: JSON.stringify(data),
    };
    return request<PublishSingleMCPResponse>(
      `/market/my-mcp/${encodeURIComponent(clientKey)}/publish`,
      opts
    );
  },
};
