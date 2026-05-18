/**
 * 我的 MCP 状态管理 Hook
 * 支持多个 MCP 并发测试，互不影响
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
  // 支持并发测试：用 Record 存储每个 clientKey 的测试结果
  const [testResults, setTestResults] = useState<Record<string, MCPTestResult>>({});
  // 用 Set 存储正在测试的 clientKeys
  const [testingKeys, setTestingKeys] = useState<Set<string>>(new Set());

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

  // 测试 MCP 连接（支持并发测试）
  const testConnection = useCallback(async (clientKey: string) => {
    // 添加到测试中的 Set
    setTestingKeys((prev) => new Set(prev).add(clientKey));
    try {
      const result = await myMcpApi.testMyMCPConnection(clientKey);
      // 存储对应 clientKey 的测试结果
      setTestResults((prev) => ({ ...prev, [clientKey]: result }));
      return result;
    } catch (err) {
      console.error("测试 MCP 连接失败:", err);
      const errorResult: MCPTestResult = {
        success: false,
        tools: [],
        error: String(err),
      };
      // 存储对应 clientKey 的错误结果
      setTestResults((prev) => ({ ...prev, [clientKey]: errorResult }));
      return errorResult;
    } finally {
      // 从测试中的 Set 移除
      setTestingKeys((prev) => {
        const next = new Set(prev);
        next.delete(clientKey);
        return next;
      });
    }
  }, []);

  // 清除指定 clientKey 的测试结果
  const clearTestResult = useCallback((clientKey: string) => {
    setTestResults((prev) => {
      const next = { ...prev };
      delete next[clientKey];
      return next;
    });
  }, []);

  // 检查指定 clientKey 是否正在测试
  const isTesting = useCallback(
    (clientKey: string) => testingKeys.has(clientKey),
    [testingKeys]
  );

  // 获取指定 clientKey 的测试结果
  const getTestResult = useCallback(
    (clientKey: string) => testResults[clientKey] ?? null,
    [testResults]
  );

  return {
    mcpList,
    selectedMCP,
    loading,
    detailLoading,
    testResults,
    testingKeys,
    refreshList,
    fetchDetail,
    createMCP,
    updateMCP,
    deleteMCP,
    toggleMCP,
    testConnection,
    clearTestResult,
    isTesting,
    getTestResult,
    setSelectedMCP,
  };
}