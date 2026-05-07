/**
 * 我的 MCP 页面，结构对齐 CmbCoworkAgent-main 的 McpPanel。
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button, Input, Spin, Tag, message } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { Plug, Search, X } from "lucide-react";
import { useMyMCP } from "./useMyMCP";
import { MCPFormModal } from "./MCPFormModal";
import { MCPDetailPanel } from "./MCPDetailPanel";
import { PublishMCPModal } from "./PublishMCPModal";
import { useIframeStore } from "../../stores/iframeStore";
import { getUserId } from "../../utils/identity";
import { DEFAULT_SOURCE_ID } from "../../constants/identity";
import type { MyMCPListItem } from "../../api/types";

export default function MyMCPPage() {
  const sourceId = useIframeStore((state) => state.source) || DEFAULT_SOURCE_ID;
  const userId = getUserId();
  const userName = useIframeStore((state) => state.clawName) || "Unknown";
  const manager = useIframeStore((state) => state.manager);
  const isSuperManager = useIframeStore((state) => state.isSuperManager);
  const canManage = manager || isSuperManager || userId === "default";

  const {
    mcpList,
    selectedMCP,
    loading,
    detailLoading,
    testResult,
    refreshList,
    fetchDetail,
    deleteMCP,
    toggleMCP,
    testConnection,
    clearTestResult,
  } = useMyMCP();

  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [formModalOpen, setFormModalOpen] = useState(false);
  const [publishModalOpen, setPublishModalOpen] = useState(false);
  const [editingClientKey, setEditingClientKey] = useState<string | null>(null);
  const [publishClientKey, setPublishClientKey] = useState<string>("");
  const [testing, setTesting] = useState(false);
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | undefined>(
    undefined
  );

  useEffect(() => {
    void refreshList();
  }, [refreshList]);

  useEffect(() => {
    return () => clearTimeout(debounceTimer.current);
  }, []);

  const handleSearchChange = useCallback((value: string) => {
    setSearchQuery(value);
    clearTimeout(debounceTimer.current);
    debounceTimer.current = setTimeout(() => setDebouncedQuery(value), 200);
  }, []);

  const filteredList = useMemo(() => {
    const q = debouncedQuery.trim().toLowerCase();
    if (!q) return mcpList;
    return mcpList.filter(
      (item) =>
        item.name.toLowerCase().includes(q) ||
        item.client_key.toLowerCase().includes(q)
    );
  }, [mcpList, debouncedQuery]);

  const isDistributed = useCallback((item: MyMCPListItem) => {
    return !!item.source && item.source.startsWith("marketplace:");
  }, []);

  const handleItemClick = useCallback(
    (item: MyMCPListItem) => {
      void fetchDetail(item.client_key);
      clearTestResult();
    },
    [fetchDetail, clearTestResult]
  );

  const handleDelete = useCallback(
    async (clientKey: string) => {
      try {
        await deleteMCP(clientKey);
        message.success("删除成功");
      } catch {
        message.error("删除失败");
      }
    },
    [deleteMCP]
  );

  const handleToggle = useCallback(
    async (clientKey: string, enabled: boolean) => {
      try {
        await toggleMCP(clientKey);
        message.success(enabled ? "已启用" : "已禁用");
      } catch {
        message.error("操作失败");
      }
    },
    [toggleMCP]
  );

  const handleTest = useCallback(async () => {
    if (!selectedMCP) return;
    setTesting(true);
    try {
      await testConnection(selectedMCP.client_key);
    } finally {
      setTesting(false);
    }
  }, [selectedMCP, testConnection]);

  const openCreateModal = useCallback(() => {
    setEditingClientKey(null);
    setFormModalOpen(true);
  }, []);

  const openEditModal = useCallback((clientKey: string) => {
    setEditingClientKey(clientKey);
    setFormModalOpen(true);
  }, []);

  const openPublishModal = useCallback((clientKey: string) => {
    setPublishClientKey(clientKey);
    setPublishModalOpen(true);
  }, []);

  return (
    <div
      style={{
        display: "flex",
        height: "100%",
        backgroundColor: "#f7f9fc",
      }}
    >
      <div
        style={{
          width: 330,
          flexShrink: 0,
          borderRight: "1px solid #eef1f5",
          display: "flex",
          flexDirection: "column",
          backgroundColor: "#ffffff",
        }}
      >
        <div style={{ padding: 12, borderBottom: "1px solid #eef1f5" }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 8,
            }}
          >
            <h2
              style={{
                fontSize: 16,
                fontWeight: 700,
                color: "#1f1f1f",
                margin: 0,
              }}
            >
              MCP 连接器
            </h2>
            <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <div
                style={{
                  minWidth: 120,
                  maxWidth: 160,
                }}
              >
                <Input
                  placeholder="搜索"
                  value={searchQuery}
                  onChange={(e) => handleSearchChange(e.target.value)}
                  prefix={
                    <Search
                      style={{
                        width: 14,
                        height: 14,
                        color: "#b8c0cc",
                      }}
                    />
                  }
                  suffix={
                    searchQuery ? (
                      <button
                        type="button"
                        onClick={() => {
                          setSearchQuery("");
                          setDebouncedQuery("");
                        }}
                        aria-label="清除搜索"
                        style={{
                          color: "#b8c0cc",
                          border: "none",
                          background: "none",
                          padding: 0,
                          cursor: "pointer",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                        }}
                      >
                        <X style={{ width: 12, height: 12 }} />
                      </button>
                    ) : null
                  }
                  style={{
                    height: 28,
                    fontSize: 12,
                    borderRadius: 8,
                    borderColor: "#e6eaf0",
                    boxShadow: "none",
                  }}
                />
              </div>
              <Button
                icon={<PlusOutlined />}
                size="small"
                style={{
                  height: 28,
                  width: 28,
                  borderRadius: 8,
                  borderColor: "transparent",
                  boxShadow: "none",
                }}
                onClick={openCreateModal}
              />
            </div>
          </div>
        </div>

        <div style={{ flex: 1, overflow: "auto", padding: 8 }}>
          {loading ? (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                padding: 32,
              }}
            >
              <Spin />
            </div>
          ) : filteredList.length === 0 ? (
            <p
              style={{
                fontSize: 12,
                color: "#8b94a3",
                padding: "4px 8px",
                margin: 0,
              }}
            >
              {mcpList.length === 0 ? "暂无连接器，点击 + 添加" : "没有匹配的连接器"}
            </p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {filteredList.map((item) => {
                const selected = selectedMCP?.client_key === item.client_key;
                return (
                  <button
                    key={item.client_key}
                    onClick={() => handleItemClick(item)}
                    style={{
                      width: "100%",
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      padding: "7px 8px",
                      borderRadius: 10,
                      border: `1px solid ${
                        selected ? "#d6e4ff" : "rgba(230,234,240,0.9)"
                      }`,
                      textAlign: "left",
                      cursor: "pointer",
                      backgroundColor: selected ? "#f3f8ff" : "transparent",
                      transition: "background-color 0.15s, border-color 0.15s",
                    }}
                  >
                    <Plug
                      style={{
                        width: 14,
                        height: 14,
                        flexShrink: 0,
                        color: item.enabled ? "#1677ff" : "#98a2b3",
                      }}
                    />
                    <span
                      style={{
                        fontSize: 14,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                        flex: 1,
                        color: item.enabled ? "#262626" : "#8b94a3",
                      }}
                    >
                      {item.name}
                    </span>
                    {isDistributed(item) && (
                      <Tag color="purple" style={{ margin: 0, fontSize: 10 }}>
                        分发
                      </Tag>
                    )}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>

      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          minWidth: 0,
          overflow: "hidden",
          backgroundColor: "#ffffff",
        }}
      >
        {detailLoading ? (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              height: "100%",
            }}
          >
            <Spin />
          </div>
        ) : (
          <MCPDetailPanel
            mcp={selectedMCP}
            testing={testing}
            testResult={testResult}
            isManager={!!canManage}
            onEdit={openEditModal}
            onDelete={(mcp) => void handleDelete(mcp.client_key)}
            onToggle={handleToggle}
            onTest={() => void handleTest()}
            onPublish={openPublishModal}
          />
        )}
      </div>

      <MCPFormModal
        open={formModalOpen}
        clientKey={editingClientKey}
        initialData={editingClientKey ? selectedMCP : null}
        onClose={() => {
          setFormModalOpen(false);
          setEditingClientKey(null);
        }}
        onSuccess={async () => {
          const editedClientKey = editingClientKey;
          setFormModalOpen(false);
          setEditingClientKey(null);
          await refreshList();
          if (editedClientKey) {
            await fetchDetail(editedClientKey);
          }
        }}
      />

      <PublishMCPModal
        open={publishModalOpen}
        sourceId={sourceId}
        userId={userId}
        userName={userName}
        clientKey={publishClientKey}
        clientName={selectedMCP?.name || ""}
        onClose={() => {
          setPublishModalOpen(false);
          setPublishClientKey("");
        }}
        onSuccess={() => {
          setPublishModalOpen(false);
          setPublishClientKey("");
          void refreshList();
        }}
      />
    </div>
  );
}
