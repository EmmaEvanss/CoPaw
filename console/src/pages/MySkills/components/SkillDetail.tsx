import { Typography, Tag, Button, Spin, message } from "antd";
import { DeleteOutlined, CheckCircleOutlined, StopOutlined } from "@ant-design/icons";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { MySkill } from "../../../api/modules/mySkills";
import { SkillFileEditor } from "./SkillFileEditor";

const { Title, Text } = Typography;

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
    setDraftContent(fileContent || "");
    setEditing(true);
  };

  const handleCancelEdit = () => {
    setEditing(false);
    setDraftContent("");
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const ok = await onSaveContent(draftContent);
      if (ok) {
        setEditing(false);
        message.success("保存成功");
      }
    } finally {
      setSaving(false);
    }
  };

  const isLoading = filePath && fileContent === null;

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
            {skill.skill_name}
          </Title>
          <div style={{ display: "flex", gap: 8 }}>
            {!editing && canEdit && fileContent !== null && (
              <Button size="small" onClick={handleStartEdit}>
                编辑
              </Button>
            )}
            <Button
              size="small"
              icon={disabled ? <CheckCircleOutlined /> : <StopOutlined />}
              onClick={onToggleEnabled}
            >
              {disabled ? "启用" : "禁用"}
            </Button>
            <Button
              size="small"
              danger
              icon={<DeleteOutlined />}
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
          />
        ) : fileContent === null ? (
          <Text type="secondary">选择文件查看内容</Text>
        ) : fileType === "markdown" ? (
          <div style={{ background: "#fafafa", padding: 16, borderRadius: 8 }}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {fileContent}
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
            {JSON.stringify(JSON.parse(fileContent), null, 2)}
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
            {fileContent}
          </pre>
        )}
      </div>
    </div>
  );
}