/**
 * 我的 MCP 状态管理 Hook
 */
import { useState, useCallback } from "react";
import { myMcpApi } from "../../api/modules/myMcp";
import type {
  MyMCPListItem,
  MyMCPDetail,
  MyMCPCreateRequest,
  MyMCPUpdateRequest,
  MCPTestResult,
} from "../../api/types";

export function useMyMCP() {
  const [mcpList, setMcpList] = useState<MyMCPListItem[]>([]);
  const [selectedMCP, setSelectedMCP] = useState<MyMCPDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [testResult, setTestResult] = useState<MCPTestResult | null>(null);
  const [testLoading, setTestLoading] = useState(false);

  // 刷新 MCP 列表
  const refreshList = useCallback(async () => {
    setLoading(true);
    try {
      const data = await myMcpApi.listMyMCP();
      setMcpList(data);
    } catch (err) {
      console.error("获取 MCP 列表失败:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  // 获取 MCP 详情
  const fetchDetail = useCallback(async (clientKey: string) => {
    setDetailLoading(true);
    try {
      const data = await myMcpApi.getMyMCPDetail(clientKey);
      setSelectedMCP(data);
    } catch (err) {
      console.error("获取 MCP 详情失败:", err);
      setSelectedMCP(null);
    } finally {
      setDetailLoading(false);
    }
  }, []);

  // 创建 MCP
  const createMCP = useCallback(async (data: MyMCPCreateRequest) => {
    try {
      const result = await myMcpApi.createMyMCP(data);
      await refreshList();
      return result;
    } catch (err) {
      console.error("创建 MCP 失败:", err);
      throw err;
    }
  }, [refreshList]);

  // 更新 MCP
  const updateMCP = useCallback(async (clientKey: string, data: MyMCPUpdateRequest) => {
    try {
      const result = await myMcpApi.updateMyMCP(clientKey, data);
      await refreshList();
      if (selectedMCP?.client_key === clientKey) {
        setSelectedMCP(result);
      }
      return result;
    } catch (err) {
      console.error("更新 MCP 失败:", err);
      throw err;
    }
  }, [refreshList, selectedMCP]);

  // 删除 MCP
  const deleteMCP = useCallback(async (clientKey: string) => {
    try {
      await myMcpApi.deleteMyMCP(clientKey);
      await refreshList();
      if (selectedMCP?.client_key === clientKey) {
        setSelectedMCP(null);
      }
    } catch (err) {
      console.error("删除 MCP 失败:", err);
      throw err;
    }
  }, [refreshList, selectedMCP]);

  // 启停 MCP
  const toggleMCP = useCallback(async (clientKey: string) => {
    try {
      const result = await myMcpApi.toggleMyMCP(clientKey);
      await refreshList();
      if (selectedMCP?.client_key === clientKey) {
        setSelectedMCP(result);
      }
      return result;
    } catch (err) {
      console.error("启停 MCP 失败:", err);
      throw err;
    }
  }, [refreshList, selectedMCP]);

  // 测试 MCP 连接
  const testConnection = useCallback(async (clientKey: string) => {
    setTestLoading(true);
    setTestResult(null);
    try {
      const result = await myMcpApi.testMyMCPConnection(clientKey);
      setTestResult(result);
      return result;
    } catch (err) {
      console.error("测试 MCP 连接失败:", err);
      const errorResult: MCPTestResult = {
        success: false,
        tools: [],
        error: String(err),
      };
      setTestResult(errorResult);
      return errorResult;
    } finally {
      setTestLoading(false);
    }
  }, []);

  // 清除测试结果
  const clearTestResult = useCallback(() => {
    setTestResult(null);
  }, []);

  return {
    mcpList,
    selectedMCP,
    loading,
    detailLoading,
    testResult,
    testLoading,
    refreshList,
    fetchDetail,
    createMCP,
    updateMCP,
    deleteMCP,
    toggleMCP,
    testConnection,
    clearTestResult,
    setSelectedMCP,
  };
}