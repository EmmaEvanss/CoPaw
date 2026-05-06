/**
 * 应用市场页面 - 技能 + MCP 双分支
 */
import { useEffect, useState, useCallback } from "react";
import {
  Input,
  Button,
  Empty,
  Spin,
  Typography,
  Tag,
  message,
  Modal,
} from "antd";
import {
  PlusOutlined,
  SearchOutlined,
  ReloadOutlined,
  ShopOutlined,
  UploadOutlined,
  ArrowLeftOutlined,
} from "@ant-design/icons";
import { SkillCard } from "./SkillCard";
import { SkillDetailDrawer } from "./SkillDetailDrawer";
import { PublishModal } from "./PublishModal";
import { DistributeModal } from "./DistributeModal";
import { MCPCard } from "./MCPCard";
import { MCPDetailDrawer } from "./MCPDetailDrawer";
import { MCPUploadModal } from "./MCPUploadModal";
import { MCPDistributeModal } from "./MCPDistributeModal";
import { MCPEditModal } from "./MCPEditModal";
import { useMarket } from "./useMarket";
import { marketApi, MarketSkill } from "../../api/modules/market";
import { marketMcpApi } from "../../api/modules/marketMcp";
import type { MarketMCPItem, MarketMCPDetail } from "../../api/types";

type ResourceType = "skill" | "mcp";

const { Title, Text } = Typography;

interface MarketSkillsProps {
  sourceId: string;
  bbkId: string;
  userId: string;
  userName: string;
  isManager: boolean;
}

export function MarketSkills({ sourceId, bbkId, userId, userName, isManager }: MarketSkillsProps) {
  const {
    categories,
    skills,
    loading: skillsLoading,
    selectedCategory,
    setSelectedCategory,
    selectedSkill,
    detailDrawerOpen,
    setDetailDrawerOpen,
    publishModalOpen,
    setPublishModalOpen,
    distributeModalOpen,
    setDistributeModalOpen,
    distributeTargetSkill,
    refreshCategories,
    refreshSkills,
    openSkillDetail,
    openDistributeModal,
  } = useMarket(sourceId, bbkId);

  // MCP 相关状态
  const [mcpList, setMcpList] = useState<MarketMCPItem[]>([]);
  const [mcpLoading, setMcpLoading] = useState(false);
  const [selectedMCP, setSelectedMCP] = useState<MarketMCPDetail | null>(null);
  const [mcpDetailMode, setMcpDetailMode] = useState<"list" | "detail">("list");
  const [mcpUploadModalOpen, setMcpUploadModalOpen] = useState(false);
  const [mcpDistributeModalOpen, setMcpDistributeModalOpen] = useState(false);
  const [distributeTargetMCP, setDistributeTargetMCP] = useState<MarketMCPItem | null>(null);
  const [mcpEditModalOpen, setMcpEditModalOpen] = useState(false);
  const [editingMCP, setEditingMCP] = useState<MarketMCPDetail | null>(null);

  const [searchQuery, setSearchQuery] = useState("");
  const [activeResourceType, setActiveResourceType] = useState<ResourceType>("skill");
  const [uploadModalOpen, setUploadModalOpen] = useState(false);

  useEffect(() => {
    refreshCategories();
    refreshSkills();
  }, [refreshCategories, refreshSkills]);

  // Handle unpublish skill
  const handleUnpublish = async (skill: MarketSkill) => {
    try {
      await marketApi.unpublishSkill(sourceId, skill.item_id, userId, userName);
      message.success("下架成功");
      refreshSkills();
    } catch (err) {
      message.error("下架失败");
    }
  };

  // Filter skills by search query
  // 刷新 MCP 列表
  const refreshMCP = useCallback(async () => {
    setMcpLoading(true);
    try {
      const data = await marketMcpApi.listMarketMCP(sourceId, bbkId, selectedCategory ?? undefined);
      setMcpList(data);
    } catch (err) {
      console.error("获取 MCP 列表失败:", err);
    } finally {
      setMcpLoading(false);
    }
  }, [sourceId, bbkId, selectedCategory]);

  // 切换资源类型时刷新
  useEffect(() => {
    if (activeResourceType === "mcp") {
      refreshMCP();
    }
  }, [activeResourceType, refreshMCP]);

  // 获取 MCP 详情
  const openMCPDetail = useCallback(async (itemId: string) => {
    try {
      const detail = await marketMcpApi.getMarketMCPDetail(sourceId, itemId, bbkId);
      if (detail) {
        setSelectedMCP(detail);
        setMcpDetailMode("detail");
      }
    } catch (err) {
      console.error("获取 MCP 详情失败:", err);
    }
  }, [sourceId, bbkId]);

  // 删除 MCP
  const handleDeleteMCP = useCallback(async (target?: MarketMCPItem | MarketMCPDetail | null) => {
    const item = target || selectedMCP;
    if (!item) return;
    try {
      await marketMcpApi.deleteMarketMCP(sourceId, item.item_id, userId, userName);
      message.success("删除成功");
      if (selectedMCP?.item_id === item.item_id) {
        setSelectedMCP(null);
        setMcpDetailMode("list");
      }
      refreshMCP();
    } catch (err) {
      console.error("删除 MCP 失败:", err);
      message.error("删除失败");
    }
  }, [sourceId, userId, userName, selectedMCP, refreshMCP]);

  const confirmDeleteMCP = useCallback((target: MarketMCPItem | MarketMCPDetail) => {
    Modal.confirm({
      title: "确认删除此 MCP？",
      content: "删除操作会直接删除市场条目，但不会影响已经分发出去的用户。",
      okText: "删除",
      okButtonProps: { danger: true },
      cancelText: "取消",
      onOk: async () => {
        await handleDeleteMCP(target);
      },
    });
  }, [handleDeleteMCP]);

  // 打开 MCP 分发弹窗
  const openMCPDistributeModal = useCallback((mcp: MarketMCPItem) => {
    setDistributeTargetMCP(mcp);
    setMcpDistributeModalOpen(true);
  }, []);

  const openMCPEditModal = useCallback(async (target: MarketMCPItem | MarketMCPDetail) => {
    try {
      const detail = "config" in target
        ? target
        : await marketMcpApi.getMarketMCPDetail(sourceId, target.item_id, bbkId);
      if (!detail) {
        message.error("未找到 MCP 详情");
        return;
      }
      setEditingMCP(detail);
      setMcpEditModalOpen(true);
    } catch (err) {
      console.error("打开 MCP 编辑弹窗失败:", err);
      message.error("打开编辑弹窗失败");
    }
  }, [bbkId, sourceId]);

  const handleMCPEditSuccess = useCallback(async (detail: MarketMCPDetail) => {
    setMcpEditModalOpen(false);
    setEditingMCP(null);
    await refreshMCP();
    if (selectedMCP?.item_id === detail.item_id) {
      try {
        const latest = await marketMcpApi.getMarketMCPDetail(sourceId, detail.item_id, bbkId);
        if (latest) {
          setSelectedMCP(latest);
        }
      } catch (err) {
        console.error("刷新编辑后的 MCP 详情失败:", err);
      }
    }
  }, [bbkId, refreshMCP, selectedMCP, sourceId]);

  // 过滤技能列表
  const filteredSkills = skills.filter((skill) => {
    const query = searchQuery.toLowerCase();
    return (
      skill.name.toLowerCase().includes(query) ||
      (skill.description?.toLowerCase().includes(query) ?? false) ||
      (skill.creator_name?.toLowerCase().includes(query) ?? false)
    );
  });

  // 过滤 MCP 列表
  const filteredMCP = mcpList.filter((mcp) => {
    const query = searchQuery.toLowerCase();
    return mcp.name.toLowerCase().includes(query);
  });

  // 按分类过滤
  const displayedSkills = selectedCategory === null
    ? filteredSkills
    : filteredSkills.filter((s) => String(s.category_id) === String(selectedCategory));

  const displayedMCP = selectedCategory === null
    ? filteredMCP
    : filteredMCP.filter((m) => {
      // MCP 暂不支持分类过滤
      return true;
    });

  // 分类计数
  const categoryCountMap = new Map<string | number, number>();
  skills.forEach((s) => {
    if (s.category_id) {
      const count = categoryCountMap.get(s.category_id) || 0;
      categoryCountMap.set(s.category_id, count + 1);
    }
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Header */}
      <div style={{ padding: 16, borderBottom: "1px solid #f0f0f0", backgroundColor: "#fff" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <ShopOutlined style={{ fontSize: 20 }} />
            <Title level={4} style={{ margin: 0 }}>应用市场</Title>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            {activeResourceType === "mcp" && (
              <Button icon={<UploadOutlined />} onClick={() => setMcpUploadModalOpen(true)}>
                上传连接器
              </Button>
            )}
            {activeResourceType === "skill" && (
              <Button icon={<UploadOutlined />}>
                上传技能
              </Button>
            )}
            {isManager && activeResourceType === "skill" && (
              <Button type="primary" icon={<PlusOutlined />} onClick={() => setPublishModalOpen(true)}>
                上架技能
              </Button>
            )}
          </div>
        </div>
        {activeResourceType === "mcp" && mcpDetailMode === "detail" ? (
          <div style={{ display: "flex", gap: 12 }}>
            <Button
              icon={<ArrowLeftOutlined />}
              onClick={() => {
                setMcpDetailMode("list");
                setSelectedMCP(null);
              }}
            >
              返回列表
            </Button>
            <Button icon={<ReloadOutlined />} onClick={refreshMCP}>
              刷新
            </Button>
          </div>
        ) : (
          <div style={{ display: "flex", gap: 12 }}>
            <Input
              placeholder={activeResourceType === "skill" ? "搜索技能名称、描述…" : "搜索 MCP 名称"}
              prefix={<SearchOutlined />}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              allowClear
              style={{ flex: 1 }}
            />
            <Button
              icon={<ReloadOutlined />}
              onClick={() => {
                if (activeResourceType === "skill") {
                  refreshCategories();
                  refreshSkills();
                } else {
                  refreshMCP();
                }
              }}
            >
              刷新
            </Button>
          </div>
        )}
        {/* 资源类型切换 */}
        <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
          <div
            onClick={() => setActiveResourceType("skill")}
            style={{
              flex: 1,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 6,
              padding: "8px 12px",
              borderRadius: 6,
              cursor: "pointer",
              border: `1px solid ${activeResourceType === "skill" ? "#d6e4ff" : "#f0f0f0"}`,
              backgroundColor: activeResourceType === "skill" ? "#e6f4ff" : "#fff",
              color: activeResourceType === "skill" ? "#1d39c4" : "#595959",
              transition: "all 0.15s ease",
            }}
          >
            <span style={{ fontWeight: 500 }}>技能</span>
          </div>
          <div
            onClick={() => setActiveResourceType("mcp")}
            style={{
              flex: 1,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 6,
              padding: "8px 12px",
              borderRadius: 6,
              cursor: "pointer",
              border: `1px solid ${activeResourceType === "mcp" ? "#b7eb8f" : "#f0f0f0"}`,
              backgroundColor: activeResourceType === "mcp" ? "#f6ffed" : "#fff",
              color: activeResourceType === "mcp" ? "#389e0d" : "#595959",
              transition: "all 0.15s ease",
            }}
          >
            <span style={{ fontWeight: 500 }}>MCP</span>
          </div>
        </div>
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflow: "hidden", display: "flex" }}>
        {activeResourceType === "skill" ? (
          <>
            {/* Sidebar - Categories */}
            <div
              style={{
                width: 200,
                borderRight: "1px solid #f0f0f0",
                padding: 16,
                overflow: "auto",
              }}
            >
              <div style={{ marginBottom: 12 }}>
                <Text strong style={{ fontSize: 14 }}>分类</Text>
                {selectedCategory !== null && (
                  <Button
                    type="link"
                    size="small"
                    style={{ fontSize: 12, padding: "0 0 0 8px" }}
                    onClick={() => setSelectedCategory(null)}
                  >
                    清除
                  </Button>
                )}
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <div
                  onClick={() => setSelectedCategory(null)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "8px 12px",
                    borderRadius: 6,
                    cursor: "pointer",
                    backgroundColor: selectedCategory === null ? "#e6f7ff" : "transparent",
                    color: selectedCategory === null ? "#1890ff" : "inherit",
                    transition: "all 0.15s ease",
                  }}
                >
                  <span>全部</span>
                  <Tag style={{ margin: 0 }}>{skills.length}</Tag>
                </div>
                {categories.map((cat) => {
                  const isActive = String(selectedCategory) === String(cat.id);
                  const count = categoryCountMap.get(cat.id) || 0;
                  return (
                    <div
                      key={cat.id}
                      onClick={() => setSelectedCategory(isActive ? null : cat.id)}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        padding: "8px 12px",
                        borderRadius: 6,
                        cursor: "pointer",
                        backgroundColor: isActive ? "#e6f7ff" : "transparent",
                        color: isActive ? "#1890ff" : "inherit",
                        transition: "all 0.15s ease",
                      }}
                    >
                      <span>{cat.name}</span>
                      <Tag style={{ margin: 0 }}>{count}</Tag>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* 技能卡片列表 */}
            <div style={{ flex: 1, padding: 16, overflow: "auto" }}>
              <div style={{ marginBottom: 12 }}>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {selectedCategory !== null
                    ? `当前分类：${categories.find((c) => String(c.id) === String(selectedCategory))?.name || "未知"}`
                    : "全部技能"}
                  {" · 筛选结果 "}
                  {displayedSkills.length} 个
                </Text>
              </div>

              {skillsLoading ? (
                <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: 200 }}>
                  <Spin />
                </div>
              ) : displayedSkills.length === 0 ? (
                <Empty description={searchQuery ? "未找到匹配的技能" : "暂无技能"} image={Empty.PRESENTED_IMAGE_SIMPLE} />
              ) : (
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(360px, 1fr))", gap: 16 }}>
                  {displayedSkills.map((skill) => (
                    <SkillCard
                      key={skill.item_id}
                      skill={skill}
                      onClick={() => openSkillDetail(skill.item_id)}
                      onDistribute={isManager ? () => openDistributeModal(skill) : undefined}
                      onUnpublish={isManager ? () => handleUnpublish(skill) : undefined}
                      isManager={isManager}
                    />
                  ))}
                </div>
              )}
            </div>
          </>
        ) : (
          /* MCP 分支 */
          <div style={{ flex: 1, padding: 16, overflow: "auto" }}>
            {mcpDetailMode === "detail" && selectedMCP ? (
              <MCPDetailDrawer
                mcp={selectedMCP}
                sourceId={sourceId}
                userId={userId}
                userName={userName}
                onDistribute={() => {
                  setDistributeTargetMCP(selectedMCP);
                  setMcpDistributeModalOpen(true);
                }}
                onEdit={() => void openMCPEditModal(selectedMCP)}
                onDelete={() => confirmDeleteMCP(selectedMCP)}
                canEdit={isManager}
              />
            ) : (
              <>
                <div style={{ marginBottom: 12 }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {"MCP 市场 · "}
                    {displayedMCP.length} 个
                  </Text>
                </div>

                {mcpLoading ? (
                  <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: 200 }}>
                    <Spin />
                  </div>
                ) : displayedMCP.length === 0 ? (
                  <Empty description={searchQuery ? "未找到匹配的 MCP" : "暂无 MCP"} image={Empty.PRESENTED_IMAGE_SIMPLE} />
                ) : (
                  <div style={{ display: "grid", gap: 16 }}>
                    {displayedMCP.map((mcp) => (
                      <MCPCard
                        key={mcp.item_id}
                        mcp={mcp}
                        onOpenDetail={() => openMCPDetail(mcp.item_id)}
                        onDistribute={() => {
                          setDistributeTargetMCP(mcp);
                          setMcpDistributeModalOpen(true);
                        }}
                        onEdit={() => void openMCPEditModal(mcp)}
                        onDelete={() => confirmDeleteMCP(mcp)}
                        canEdit={isManager}
                      />
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>

      {/* 技能详情抽屉 */}
      <SkillDetailDrawer
        open={detailDrawerOpen}
        skill={selectedSkill}
        onClose={() => setDetailDrawerOpen(false)}
        isManager={isManager}
        sourceId={sourceId}
        userId={userId}
        userName={userName}
        onRefresh={refreshSkills}
      />

      {/* 技能上架弹窗 */}
      {isManager && (
        <>
          <PublishModal
            open={publishModalOpen}
            sourceId={sourceId}
            userId={userId}
            userName={userName}
            onClose={() => setPublishModalOpen(false)}
            onSuccess={refreshSkills}
          />
          <DistributeModal
            open={distributeModalOpen}
            skill={distributeTargetSkill}
            sourceId={sourceId}
            userId={userId}
            userName={userName}
            onClose={() => setDistributeModalOpen(false)}
            onSuccess={refreshSkills}
          />
        </>
      )}

      {/* MCP 上传弹窗 */}
      <MCPUploadModal
        open={mcpUploadModalOpen}
        sourceId={sourceId}
        userId={userId}
        userName={userName}
        onClose={() => setMcpUploadModalOpen(false)}
        onSuccess={refreshMCP}
      />

      {/* MCP 分发弹窗 */}
      <MCPDistributeModal
        open={mcpDistributeModalOpen}
        mcp={distributeTargetMCP}
        sourceId={sourceId}
        userId={userId}
        userName={userName}
        onClose={() => { setMcpDistributeModalOpen(false); setDistributeTargetMCP(null); }}
        onSuccess={() => {
          setMcpDistributeModalOpen(false);
          setDistributeTargetMCP(null);
          refreshMCP();
        }}
      />

      <MCPEditModal
        open={mcpEditModalOpen}
        mcp={editingMCP}
        sourceId={sourceId}
        userId={userId}
        userName={userName}
        onClose={() => {
          setMcpEditModalOpen(false);
          setEditingMCP(null);
        }}
        onSuccess={(detail) => {
          void handleMCPEditSuccess(detail);
        }}
      />
    </div>
  );
}
