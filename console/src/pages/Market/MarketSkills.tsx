import { useEffect, useState } from "react";
import { Input, Button, Empty, Spin, Typography, Tag } from "antd";
import { PlusOutlined, SearchOutlined, ReloadOutlined, ShopOutlined, UploadOutlined, ThunderboltOutlined, ApiOutlined } from "@ant-design/icons";
import { SkillCard } from "./SkillCard";
import { SkillDetailDrawer } from "./SkillDetailDrawer";
import { PublishModal } from "./PublishModal";
import { DistributeModal } from "./DistributeModal";
import { useMarket } from "./useMarket";
import { MarketSkill } from "../../api/modules/market";

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
    loading,
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

  const [searchQuery, setSearchQuery] = useState("");
  const [activeResourceType, setActiveResourceType] = useState<ResourceType>("skill");

  useEffect(() => {
    refreshCategories();
    refreshSkills();
  }, [refreshCategories, refreshSkills]);

  // Filter skills by search query
  const filteredSkills = skills.filter((skill) => {
    const query = searchQuery.toLowerCase();
    return (
      skill.name.toLowerCase().includes(query) ||
      (skill.description?.toLowerCase().includes(query) ?? false) ||
      (skill.creator_name?.toLowerCase().includes(query) ?? false)
    );
  });

  // Filter by selected category
  const displayedSkills = selectedCategory === null
    ? filteredSkills
    : filteredSkills.filter((s) => String(s.category_id) === String(selectedCategory));

  // Calculate category counts
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
            <Button icon={<UploadOutlined />}>
              上传技能
            </Button>
            {isManager && (
              <Button type="primary" icon={<PlusOutlined />} onClick={() => setPublishModalOpen(true)}>
                上架技能
              </Button>
            )}
          </div>
        </div>
        <div style={{ display: "flex", gap: 12 }}>
          <Input
            placeholder={activeResourceType === "skill" ? "搜索技能名称、描述…" : "搜索MCP名称、描述…"}
            prefix={<SearchOutlined />}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            allowClear
            style={{ flex: 1 }}
          />
          <Button icon={<ReloadOutlined />} onClick={() => { refreshCategories(); refreshSkills(); }}>
            刷新
          </Button>
        </div>
        {/* Resource type toggle */}
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
            <ThunderboltOutlined style={{ color: activeResourceType === "skill" ? "#1890ff" : "#8c8c8c" }} />
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
            <ApiOutlined style={{ color: activeResourceType === "mcp" ? "#52c41a" : "#8c8c8c" }} />
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
                {/* All category */}
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
                {/* Category items */}
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

            {/* Main content - Skill cards */}
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

              {loading ? (
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
                      isManager={isManager}
                    />
                  ))}
                </div>
              )}
            </div>
          </>
        ) : (
          /* MCP placeholder */
          <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={
                <span>
                  MCP 市场 · 功能开发中，敬请期待
                </span>
              }
            />
          </div>
        )}
      </div>

      <SkillDetailDrawer
        open={detailDrawerOpen}
        skill={selectedSkill}
        onClose={() => setDetailDrawerOpen(false)}
      />
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
    </div>
  );
}