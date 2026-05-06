import { Typography, Tag } from "antd";
import { DownOutlined, RightOutlined } from "@ant-design/icons";
import { useState, useEffect } from "react";
import { MySkill, FileTreeNode, mySkillsApi } from "../../../api/modules/mySkills";
import { SkillFileTree } from "./SkillFileTree";

const { Text } = Typography;

interface Props {
  skill: MySkill;
  expanded: boolean;
  selected: boolean;
  disabled: boolean;
  sourceId: string;
  userId: string;
  userName: string;
  bbkId: string;
  selectedFile: string | null;
  expandedDirs: Set<string>;
  onToggle: () => void;
  onSelectFile: (path: string) => void;
  onToggleDir: (path: string) => void;
}

export function SkillItem({
  skill,
  expanded,
  selected,
  disabled,
  sourceId,
  userId,
  userName,
  bbkId,
  selectedFile,
  expandedDirs,
  onToggle,
  onSelectFile,
  onToggleDir,
}: Props) {
  const [files, setFiles] = useState<FileTreeNode[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (expanded && files.length === 0) {
      setLoading(true);
      mySkillsApi.listSkillFiles(sourceId, userId, userName, bbkId, skill.skill_name)
        .then(setFiles)
        .catch(console.error)
        .finally(() => setLoading(false));
    }
  }, [expanded, skill.skill_name, sourceId, userId, userName, bbkId, files.length]);

  return (
    <div
      style={{
        borderRadius: 8,
        border: "1px solid #f0f0f0",
        marginBottom: 8,
        overflow: "hidden",
        backgroundColor: selected ? "#e6f4ff" : "#fff",
      }}
    >
      <div
        onClick={onToggle}
        style={{
          display: "flex",
          alignItems: "center",
          padding: "10px 12px",
          cursor: "pointer",
          borderBottom: expanded ? "1px solid #f0f0f0" : "none",
        }}
      >
        {expanded ? (
          <DownOutlined
            style={{ fontSize: 10, marginRight: 8, color: "#8c8c8c" }}
          />
        ) : (
          <RightOutlined
            style={{ fontSize: 10, marginRight: 8, color: "#8c8c8c" }}
          />
        )}
        <Text
          strong={selected}
          style={{
            flex: 1,
            textDecoration: disabled ? "line-through" : "none",
            color: disabled ? "#8c8c8c" : "#262626",
          }}
        >
          {skill.skill_name}
        </Text>
        {skill.version && <Tag style={{ marginLeft: 4 }}>v{skill.version}</Tag>}
        {skill.is_received && <Tag color="orange">接收的</Tag>}
        {skill.has_update && <Tag color="red">有更新</Tag>}
      </div>
      {expanded && (
        <div style={{ padding: "8px 0" }}>
          {loading ? (
            <Text type="secondary" style={{ padding: "0 16px" }}>
              加载中...
            </Text>
          ) : files.length === 0 ? (
            <Text type="secondary" style={{ padding: "0 16px" }}>
              没有文件
            </Text>
          ) : (
            <SkillFileTree
              nodes={files}
              level={0}
              skillName={skill.skill_name}
              expandedDirs={expandedDirs}
              selectedFile={selectedFile}
              onToggleDir={onToggleDir}
              onSelectFile={onSelectFile}
            />
          )}
        </div>
      )}
    </div>
  );
}