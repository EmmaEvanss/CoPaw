import { Typography } from "antd";
import {
  FolderOutlined,
  FileOutlined,
  DownOutlined,
  RightOutlined,
} from "@ant-design/icons";
import { FileTreeNode } from "../../../api/modules/mySkills";

const { Text } = Typography;

interface Props {
  nodes: FileTreeNode[];
  level: number;
  skillName: string;
  expandedDirs: Set<string>;
  selectedFile: string | null;
  onToggleDir: (path: string) => void;
  onSelectFile: (path: string) => void;
}

export function SkillFileTree({
  nodes,
  level,
  skillName,
  expandedDirs,
  selectedFile,
  onToggleDir,
  onSelectFile,
}: Props) {
  return (
    <div>
      {nodes.map((node) => {
        const paddingLeft = 16 + level * 16;
        const isExpanded = expandedDirs.has(node.path);
        const isSelected = selectedFile === node.path;

        if (node.type === "directory") {
          return (
            <div key={node.path}>
              <div
                onClick={() => onToggleDir(node.path)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  padding: "6px 8px",
                  paddingLeft,
                  cursor: "pointer",
                  borderRadius: 4,
                  marginBottom: 2,
                  backgroundColor: isExpanded ? "#f5f5f5" : "transparent",
                }}
              >
                {isExpanded ? (
                  <DownOutlined
                    style={{ fontSize: 10, marginRight: 6, color: "#8c8c8c" }}
                  />
                ) : (
                  <RightOutlined
                    style={{ fontSize: 10, marginRight: 6, color: "#8c8c8c" }}
                  />
                )}
                <FolderOutlined
                  style={{ fontSize: 14, marginRight: 6, color: "#faad14" }}
                />
                <Text style={{ fontSize: 13 }}>{node.name}</Text>
              </div>
              {isExpanded && node.children && (
                <SkillFileTree
                  nodes={node.children}
                  level={level + 1}
                  skillName={skillName}
                  expandedDirs={expandedDirs}
                  selectedFile={selectedFile}
                  onToggleDir={onToggleDir}
                  onSelectFile={onSelectFile}
                />
              )}
            </div>
          );
        }

        return (
          <div
            key={node.path}
            onClick={() => onSelectFile(node.path)}
            style={{
              display: "flex",
              alignItems: "center",
              padding: "6px 8px",
              paddingLeft: paddingLeft + 16,
              cursor: "pointer",
              borderRadius: 4,
              marginBottom: 2,
              backgroundColor: isSelected ? "#e6f4ff" : "transparent",
              border: isSelected
                ? "1px solid #1890ff"
                : "1px solid transparent",
            }}
          >
            <FileOutlined
              style={{ fontSize: 14, marginRight: 6, color: "#8c8c8c" }}
            />
            <Text
              style={{
                fontSize: 13,
                color: isSelected ? "#1890ff" : "#262626",
              }}
            >
              {node.name}
            </Text>
          </div>
        );
      })}
    </div>
  );
}