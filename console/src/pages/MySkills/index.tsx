import { useEffect, useState, useRef } from "react";
import { Typography, Card, Spin, Button, Space, Input, message, Tag, Empty } from "antd";
import { PlusOutlined, UploadOutlined, ShopOutlined, RightOutlined, DownOutlined, FolderOutlined, FileOutlined, StarOutlined, SearchOutlined } from "@ant-design/icons";
import { useMySkills } from "./useMySkills";
import { useIframeStore } from "../../stores/iframeStore";
import { getUserId } from "../../utils/identity";
import { DEFAULT_SOURCE_ID } from "../../constants/identity";
import { MySkill } from "../../api/modules/mySkills";

const { Title, Text } = Typography;

export default function MySkillsPage() {
  const sourceId = useIframeStore((state) => state.source) || DEFAULT_SOURCE_ID;
  const bbkId = useIframeStore((state) => state.bbk) || "100";
  const isManager = useIframeStore((state) => state.manager) || false;
  const userId = getUserId();
  const { createdSkills, receivedSkills, loading, refresh } = useMySkills(sourceId, userId);
  const [searchText, setSearchText] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [selectedSkill, setSelectedSkill] = useState<MySkill | null>(null);
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set(["created", "received"]));
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Debounce search
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const handleSearchChange = (value: string) => {
    setSearchText(value);
    clearTimeout(debounceTimer.current);
    debounceTimer.current = setTimeout(() => setDebouncedQuery(value), 200);
  };

  useEffect(() => {
    refresh();
    return () => clearTimeout(debounceTimer.current);
  }, [refresh]);

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    message.info(`上传功能开发中: ${file.name}`);
    e.target.value = "";
  };

  // Filter skills
  const filterSkills = (skills: MySkill[]) => {
    const q = debouncedQuery.trim().toLowerCase();
    if (!q) return skills;
    return skills.filter((s) =>
      s.skill_name.toLowerCase().includes(q) ||
      (s.description?.toLowerCase().includes(q) ?? false)
    );
  };

  const filteredCreated = filterSkills(createdSkills);
  const filteredReceived = filterSkills(receivedSkills);

  const toggleGroup = (key: string) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const handleSelectSkill = (skill: MySkill) => {
    setSelectedSkill(skill);
  };

  // Navigate to marketplace (would need to be implemented with routing)
  const goToMarketplace = () => {
    message.info("跳转到应用市场功能开发中");
  };

  // Skill list item component
  const SkillListItem = ({ skill, isSelected }: { skill: MySkill; isSelected: boolean }) => (
    <div
      onClick={() => handleSelectSkill(skill)}
      style={{
        padding: "8px 10px",
        borderRadius: 6,
        cursor: "pointer",
        backgroundColor: isSelected ? "#e6f4ff" : "transparent",
        border: isSelected ? "1px solid #1890ff" : "1px solid transparent",
        marginBottom: 4,
        transition: "all 0.15s ease",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
        <FileOutlined style={{ color: "#8c8c8c", flexShrink: 0 }} />
        <Text
          strong={isSelected}
          style={{
            flex: 1,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            color: isSelected ? "#1890ff" : "#262626",
          }}
        >
          {skill.skill_name}
        </Text>
        {skill.version && (
          <Tag style={{ fontSize: 10, margin: 0, borderRadius: 4 }}>v{skill.version}</Tag>
        )}
      </div>
    </div>
  );

  // Skill group section
  const SkillGroup = ({
    title,
    skills,
    groupKey,
    style,
  }: {
    title: string;
    skills: MySkill[];
    groupKey: string;
    style?: React.CSSProperties;
  }) => {
    const isExpanded = expandedGroups.has(groupKey);

    const headerStyle = (() => {
      if (title.includes("创建")) {
        return {
          borderColor: "#d6e4ff",
          backgroundColor: "#e6f4ff",
          color: "#1d39c4",
          dotColor: "#1890ff",
        };
      }
      if (title.includes("接收")) {
        return {
          borderColor: "#b7eb8f",
          backgroundColor: "#f6ffed",
          color: "#389e0d",
          dotColor: "#52c41a",
        };
      }
      return {
        borderColor: "#d9d9d9",
        backgroundColor: "#f5f5f5",
        color: "#595959",
        dotColor: "#8c8c8c",
      };
    })();

    return (
      <div
        style={{
          borderRadius: 8,
          border: "1px solid #f0f0f0",
          backgroundColor: "#fff",
          padding: 6,
          ...style,
        }}
      >
        <div
          onClick={() => toggleGroup(groupKey)}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "6px 10px",
            borderRadius: 6,
            cursor: "pointer",
            border: `1px solid ${headerStyle.borderColor}`,
            backgroundColor: headerStyle.backgroundColor,
            transition: "background-color 0.15s ease",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
            {isExpanded ? (
              <DownOutlined style={{ fontSize: 12, color: "#8c8c8c" }} />
            ) : (
              <RightOutlined style={{ fontSize: 12, color: "#8c8c8c" }} />
            )}
            <div
              style={{
                width: 6,
                height: 6,
                borderRadius: "50%",
                backgroundColor: headerStyle.dotColor,
                flexShrink: 0,
              }}
            />
            <Text style={{ fontSize: 13, fontWeight: 500, color: headerStyle.color }}>
              {title}
            </Text>
          </div>
          <Tag
            style={{
              height: 20,
              minWidth: 24,
              justifyContent: "center",
              padding: "0 6px",
              fontSize: 11,
              fontWeight: 500,
              margin: 0,
              borderRadius: 4,
              backgroundColor: "#fff",
              border: `1px solid ${headerStyle.borderColor}`,
              color: headerStyle.color,
            }}
          >
            {skills.length}
          </Tag>
        </div>
        {isExpanded && (
          <div style={{ padding: "8px 2px 2px 2px" }}>
            {skills.length === 0 ? (
              <Text style={{ fontSize: 12, color: "#8c8c8c", padding: "8px 10px", display: "block" }}>
                没有匹配的技能
              </Text>
            ) : (
              skills.map((skill) => (
                <SkillListItem
                  key={skill.skill_name}
                  skill={skill}
                  isSelected={selectedSkill?.skill_name === skill.skill_name}
                />
              ))
            )}
          </div>
        )}
      </div>
    );
  };

  // Skill detail panel
  const SkillDetailPanel = ({ skill }: { skill: MySkill | null }) => {
    if (!skill) {
      return (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", padding: 32, textAlign: "center" }}>
          <StarOutlined style={{ fontSize: 48, color: "#faad14", marginBottom: 16 }} />
          <Title level={5} style={{ margin: "0 0 8px 0", color: "#262626" }}>
            技能详情
          </Title>
          <Text type="secondary" style={{ fontSize: 14 }}>
            选择左侧技能查看详情
          </Text>
        </div>
      );
    }

    return (
      <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
        {/* Header */}
        <div
          style={{
            padding: 16,
            borderBottom: "1px solid #f0f0f0",
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            gap: 12,
          }}
        >
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginBottom: 8 }}>
              <Text strong style={{ fontSize: 16, color: "#262626" }}>
                {skill.skill_name}
              </Text>
              {skill.version && (
                <Tag style={{ fontSize: 11, borderRadius: 4 }}>v{skill.version}</Tag>
              )}
              {skill.source === "customized" && (
                <Tag color="green" style={{ fontSize: 11, borderRadius: 4 }}>自定义</Tag>
              )}
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
              {skill.category && (
                <Tag style={{ fontSize: 11, borderRadius: 4, backgroundColor: "#f5f5f5", border: "1px solid #d9d9d9" }}>
                  {skill.category}
                </Tag>
              )}
              {skill.creator_name && (
                <Text type="secondary" style={{ fontSize: 12 }}>
                  创建者: {skill.creator_name}
                </Text>
              )}
            </div>
          </div>
        </div>

        {/* Description */}
        <div style={{ padding: "12px 16px", borderBottom: "1px solid #f0f0f0" }}>
          <Text type="secondary" style={{ fontSize: 14, whiteSpace: "pre-wrap" }}>
            {skill.description || "暂无描述"}
          </Text>
        </div>

        {/* Content placeholder */}
        <div style={{ flex: 1, padding: 16, overflow: "auto" }}>
          <div
            style={{
              borderRadius: 8,
              border: "1px solid #f0f0f0",
              backgroundColor: "#f5f5f5",
              padding: 16,
              minHeight: 200,
            }}
          >
            <Text type="secondary" style={{ fontSize: 12 }}>
              技能内容预览功能开发中…
            </Text>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div style={{ display: "flex", height: "100%", backgroundColor: "#fff" }}>
      {/* Left sidebar */}
      <div
        style={{
          width: 300,
          flexShrink: 0,
          borderRight: "1px solid #f0f0f0",
          display: "flex",
          flexDirection: "column",
        }}
      >
        {/* Search and actions */}
        <div style={{ padding: 16, borderBottom: "1px solid #f0f0f0" }}>
          <Input
            placeholder="搜索技能"
            prefix={<SearchOutlined />}
            value={searchText}
            onChange={(e) => handleSearchChange(e.target.value)}
            allowClear
            style={{ marginBottom: 8 }}
          />
          <div style={{ display: "flex", gap: 8 }}>
            <Button
              icon={<UploadOutlined />}
              onClick={handleUploadClick}
              style={{ flex: 1 }}
            >
              上传技能
            </Button>
            <Button
              icon={<ShopOutlined />}
              onClick={goToMarketplace}
              style={{ flex: 1 }}
            >
              去应用市场
              <RightOutlined style={{ fontSize: 10, marginLeft: 4 }} />
            </Button>
          </div>
        </div>

        {/* Skill groups */}
        <div style={{ flex: 1, overflow: "auto", padding: 8 }}>
          {loading ? (
            <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: 100 }}>
              <Spin />
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <SkillGroup
                title="我创建的"
                skills={filteredCreated}
                groupKey="created"
              />
              <SkillGroup
                title="我接收的"
                skills={filteredReceived}
                groupKey="received"
              />
            </div>
          )}
        </div>
      </div>

      {/* Right detail panel */}
      <div style={{ flex: 1, backgroundColor: "#fff", overflow: "hidden" }}>
        <SkillDetailPanel skill={selectedSkill} />
      </div>

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".zip"
        style={{ display: "none" }}
        onChange={handleFileSelect}
      />
    </div>
  );
}
