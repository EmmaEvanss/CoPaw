/**
 * 市场 MCP API（调用市场服务）
 */
import { request } from "../request";
import { buildAuthHeaders } from "../authHeaders";
import type {
  MarketMCPItem,
  MarketMCPDetail,
  MCPUploadRequest,
  MCPDistributeRequest,
  MCPDistributeResponse,
  MCPTestResult,
  UpdateMarketMCPMetadataRequest,
} from "../types";

function mergeHeaders(extra?: Record<string, string>): RequestInit {
  const base = buildAuthHeaders();
  const merged: Record<string, string> = { ...base, ...(extra || {}) };
  return { headers: new Headers(merged) };
}

export const marketMcpApi = {
  /**
   * 获取市场 MCP 列表
   */
  listMarketMCP: async (
    sourceId: string,
    bbkId: string,
    categoryId?: number
  ): Promise<MarketMCPItem[]> => {
    const resolvedSourceId = sourceId || "default";
    let url = "/market/mcp";
    const params = new URLSearchParams();
    if (categoryId !== undefined) {
      params.append("category_id", String(categoryId));
    }
    if (params.toString()) {
      url += `?${params.toString()}`;
    }
    const opts = mergeHeaders({
      "X-Source-Id": resolvedSourceId,
      "X-Bbk-Id": bbkId,
    });
    return request<MarketMCPItem[]>(url, opts);
  },

  /**
   * 获取市场 MCP 详情
   */
  getMarketMCPDetail: async (
    sourceId: string,
    itemId: string,
    bbkId: string
  ): Promise<MarketMCPDetail | null> => {
    const resolvedSourceId = sourceId || "default";
    const opts = mergeHeaders({
      "X-Source-Id": resolvedSourceId,
      "X-Bbk-Id": bbkId,
    });
    return request<MarketMCPDetail | null>(
      `/market/mcp/${itemId}`,
      opts
    );
  },

  /**
   * 上传 MCP 到市场（管理员）
   */
  uploadMCP: async (
    sourceId: string,
    userId: string,
    userName: string,
    data: MCPUploadRequest
  ): Promise<MarketMCPItem> => {
    const resolvedSourceId = sourceId || "default";
    const formData = new FormData();
    formData.append("file", data.file);
    formData.append("name", data.name);
    if (data.chinese_name) {
      formData.append("chinese_name", data.chinese_name);
    }
    if (data.description) {
      formData.append("description", data.description);
    }
    if (data.guidance) {
      formData.append("guidance", data.guidance);
    }
    if (data.bbk_ids && data.bbk_ids.length > 0) {
      formData.append("bbk_ids", JSON.stringify(data.bbk_ids));
    }
    const opts: RequestInit = {
      method: "POST",
      headers: new Headers({
        "X-Source-Id": resolvedSourceId,
        "X-User-Id": userId,
        "X-User-Name": encodeURIComponent(userName),
        "X-Manager": "true",
      }),
      body: formData,
    };
    return request<MarketMCPItem>("/market/mcp/upload", opts);
  },

  /**
   * 分发 MCP 到用户（管理员）
   */
  distributeMCP: async (
    sourceId: string,
    itemId: string,
    userId: string,
    userName: string,
    data: MCPDistributeRequest
  ): Promise<MCPDistributeResponse> => {
    const resolvedSourceId = sourceId || "default";
    const opts: RequestInit = {
      method: "POST",
      headers: new Headers({
        "Content-Type": "application/json",
        "X-Source-Id": resolvedSourceId,
        "X-User-Id": userId,
        "X-User-Name": encodeURIComponent(userName),
        "X-Manager": "true",
      }),
      body: JSON.stringify(data),
    };
    return request<MCPDistributeResponse>(
      `/market/mcp/${itemId}/distribute`,
      opts
    );
  },

  /**
   * 删除市场 MCP（管理员）
   */
  deleteMarketMCP: async (
    sourceId: string,
    itemId: string,
    userId: string,
    userName: string
  ): Promise<void> => {
    const resolvedSourceId = sourceId || "default";
    const opts: RequestInit = {
      method: "DELETE",
      headers: new Headers({
        "X-Source-Id": resolvedSourceId,
        "X-User-Id": userId,
        "X-User-Name": encodeURIComponent(userName),
        "X-Manager": "true",
      }),
    };
    return request<void>(`/market/mcp/${itemId}`, opts);
  },

  /**
   * 测试市场 MCP 连接（管理员）
   */
  testMarketMCP: async (
    sourceId: string,
    itemId: string,
    userId: string,
    userName: string
  ): Promise<MCPTestResult> => {
    const resolvedSourceId = sourceId || "default";
    const opts: RequestInit = {
      method: "POST",
      headers: new Headers({
        "X-Source-Id": resolvedSourceId,
        "X-User-Id": userId,
        "X-User-Name": encodeURIComponent(userName),
        "X-Manager": "true",
      }),
    };
    return request<MCPTestResult>(`/market/mcp/${itemId}/test`, opts);
  },

  /**
   * 更新市场 MCP 元数据（管理员）
   */
  updateMarketMCPMetadata: async (
    sourceId: string,
    itemId: string,
    userId: string,
    userName: string,
    data: UpdateMarketMCPMetadataRequest,
  ): Promise<MarketMCPDetail> => {
    const resolvedSourceId = sourceId || "default";
    const opts: RequestInit = {
      method: "PUT",
      headers: new Headers({
        "Content-Type": "application/json",
        "X-Source-Id": resolvedSourceId,
        "X-User-Id": userId,
        "X-User-Name": encodeURIComponent(userName),
        "X-Manager": "true",
      }),
      body: JSON.stringify(data),
    };
    return request<MarketMCPDetail>(`/market/mcp/${itemId}/metadata`, opts);
  },
};
