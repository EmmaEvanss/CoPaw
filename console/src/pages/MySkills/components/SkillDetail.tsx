import { Typography, Tag, Button, Spin, message } from "antd";
import { Power, Trash2, Pencil } from "lucide-react";
import { useState, useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { MySkill } from "../../../api/modules/mySkills";
import { SkillFileEditor } from "./SkillFileEditor";

const { Title, Text } = Typography;

/**
 * 将 Markdown 文件内容分割为 frontmatter 和正文。
 * frontmatter（位于 --- 分隔符之间）作为 protectedPrefix 被保护，
 * 只允许编辑后面的正文内容 editableContent。
 */
function splitMarkdownFrontmatter(
  filePath: string | null,
  content: string | null
): { protectedPrefix: string; editableContent: string; hasFrontmatter: boolean } {
  const isMarkdown = !!filePath && /\.md$/i.test(filePath);
  if (!isMarkdown || typeof content !== "string") {
    return { protectedPrefix: "", editableContent: content ?? "", hasFrontmatter: false };
  }

  const match = content.match(/^---\r?\n[\s\S]*?\r?\n---[ \t]*(?:\r?\n|$)/);
  if (!match) {
    return { protectedPrefix: "", editableContent: content, hasFrontmatter: false };
  }

  return {
    protectedPrefix: match[0],
    editableContent: content.slice(match[0].length),
    hasFrontmatter: true,
  };
}

/**
 * 将 protectedPrefix (frontmatter) 和 editableContent 合并为完整文件内容。
 */
function mergeMarkdownFrontmatter(protectedPrefix: string, editableContent: string): string {
  if (!protectedPrefix) return editableContent;
  if (!editableContent || protectedPrefix.endsWith("\n") || protectedPrefix.endsWith("\r\n")) {
    return `${protectedPrefix}${editableContent}`;
  }
  return `${protectedPrefix}\n${editableContent}`;
}

interface Props {
  skill: MySkill | null;
  fileContent: string | null;
  fileType: string | null;
  filePath: string | null;
  canEdit: boolean;
  disabled: boolean;
  onToggleEnabled: () => void;
  onDelete: () => void;
  onSaveContent: (content: string) => Promise<boolean>;
}

export function SkillDetail({
  skill,
  fileContent,
  fileType,
  filePath,
  canEdit,
  disabled,
  onToggleEnabled,
  onDelete,
  onSaveContent,
}: Props) {
  const [editing, setEditing] = useState(false);
  const [draftContent, setDraftContent] = useState("");
  const [saving, setSaving] = useState(false);

  const markdownFrontmatter = useMemo(
    () => splitMarkdownFrontmatter(filePath, fileContent),
    [filePath, fileContent]
  );

  if (!skill) {
    return (
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          height: "100%",
          padding: 32,
          textAlign: "center",
        }}
      >
        <Title level={5} style={{ margin: "0 0 8px 0" }}>
          技能详情
        </Title>
        <Text type="secondary">选择左侧技能查看详情</Text>
      </div>
    );
  }

  const handleStartEdit = () => {
    setDraftContent(markdownFrontmatter.editableContent);
    setEditing(true);
  };

  const handleCancelEdit = () => {
    setEditing(false);
    setDraftContent(markdownFrontmatter.editableContent);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const fullContent = mergeMarkdownFrontmatter(
        markdownFrontmatter.protectedPrefix,
        draftContent
      );
      const ok = await onSaveContent(fullContent);
      if (ok) {
        setEditing(false);
        message.success("保存成功");
      }
    } finally {
      setSaving(false);
    }
  };

  const isLoading = filePath && fileContent === null;

  const previewContent =
    fileType === "markdown" && markdownFrontmatter.hasFrontmatter
      ? markdownFrontmatter.editableContent.trim()
      : fileContent;

  const editNote = markdownFrontmatter.hasFrontmatter
    ? "Markdown 顶部元信息受保护，此处只编辑正文内容。"
    : null;

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      {/* Header */}
      <div style={{ padding: 16, borderBottom: "1px solid #f0f0f0" }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: 8,
          }}
        >
          <Title level={4} style={{ margin: 0 }}>
            {skill.display_name || skill.skill_name}
          </Title>
          <div style={{ display: "flex", gap: 8 }}>
            {!editing && canEdit && fileContent !== null && (
              <Button
                size="small"
                icon={<Pencil style={{ width: 12, height: 12 }} />}
                style={{ height: 28, fontSize: 12, borderRadius: 8 }}
                onClick={handleStartEdit}
              >
                编辑
              </Button>
            )}
            <Button
              size="small"
              type={skill.enabled ? "primary" : "default"}
              icon={<Power style={{ width: 12, height: 12 }} />}
              style={{ height: 28, fontSize: 12, borderRadius: 8 }}
              onClick={onToggleEnabled}
            >
              {skill.enabled ? "已启用" : "已禁用"}
            </Button>
            <Button
              size="small"
              danger
              icon={<Trash2 style={{ width: 12, height: 12 }} />}
              style={{ height: 28, fontSize: 12, borderRadius: 8 }}
              onClick={onDelete}
            >
              删除
            </Button>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {skill.version && <Tag color="blue">v{skill.version}</Tag>}
          {skill.source === "customized" && <Tag color="green">自定义</Tag>}
          {skill.is_received && <Tag color="orange">接收的</Tag>}
          {disabled && <Tag color="red">已禁用</Tag>}
        </div>
      </div>

      {/* Description */}
      <div
        style={{
          padding: "12px 16px",
          borderBottom: "1px solid #f0f0f0",
        }}
      >
        <Text type="secondary">{skill.description || "暂无描述"}</Text>
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflow: "auto", padding: 16 }}>
        {isLoading ? (
          <Spin />
        ) : editing ? (
          <SkillFileEditor
            content={draftContent}
            fileType={fileType || "text"}
            onChange={setDraftContent}
            onSave={handleSave}
            onCancel={handleCancelEdit}
            saving={saving}
            note={editNote}
          />
        ) : previewContent === null ? (
          <Text type="secondary">选择文件查看内容</Text>
        ) : fileType === "markdown" ? (
          <div style={{ background: "#fafafa", padding: 16, borderRadius: 8 }}>
            {markdownFrontmatter.hasFrontmatter && (
              <p
                style={{
                  fontSize: 12,
                  color: "#874d00",
                  marginBottom: 12,
                  padding: "4px 8px",
                  backgroundColor: "#fff7e6",
                  border: "1px solid #ffd591",
                  borderRadius: 4,
                }}
              >
                文件顶部包含受保护的元信息，此处只显示正文内容。
              </p>
            )}
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {previewContent}
            </ReactMarkdown>
          </div>
        ) : fileType === "json" ? (
          <pre
            style={{
              background: "#fafafa",
              padding: 16,
              borderRadius: 8,
              overflow: "auto",
              fontSize: 12,
            }}
          >
            {JSON.stringify(JSON.parse(previewContent), null, 2)}
          </pre>
        ) : (
          <pre
            style={{
              background: "#fafafa",
              padding: 16,
              borderRadius: 8,
              overflow: "auto",
              fontSize: 12,
            }}
          >
            {previewContent}
          </pre>
        )}
      </div>
    </div>
  );
}