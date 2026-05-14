import { Input, Button, Space } from "antd";
import { SaveOutlined, CloseOutlined, EditOutlined } from "@ant-design/icons";

const { TextArea } = Input;

interface Props {
  content: string;
  fileType: string;
  onChange: (content: string) => void;
  onSave: () => void;
  onCancel: () => void;
  saving: boolean;
  note?: string | null;
}

export function SkillFileEditor({
  content,
  fileType,
  onChange,
  onSave,
  onCancel,
  saving,
  note,
}: Props) {
  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <div
        style={{
          marginBottom: 12,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 8,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              fontSize: 11,
              color: "#874d00",
              backgroundColor: "#fff7e6",
              border: "1px solid #ffd591",
              borderRadius: 4,
              padding: "2px 8px",
            }}
          >
            <EditOutlined style={{ fontSize: 12 }} />
            编辑模式
          </span>
          <span style={{ fontSize: 12, color: "#8c8c8c" }}>
            {fileType === "markdown"
              ? "Markdown"
              : fileType === "json"
                ? "JSON"
                : "文本"}
          </span>
        </div>
        <Space>
          <Button
            size="small"
            icon={<CloseOutlined />}
            onClick={onCancel}
            disabled={saving}
          >
            取消
          </Button>
          <Button
            size="small"
            type="primary"
            icon={<SaveOutlined />}
            onClick={onSave}
            loading={saving}
          >
            保存
          </Button>
        </Space>
      </div>
      {note && (
        <p
          style={{
            fontSize: 12,
            color: "#874d00",
            marginBottom: 8,
          }}
        >
          {note}
        </p>
      )}
      <TextArea
        value={content}
        onChange={(e) => onChange(e.target.value)}
        style={{
          flex: 1,
          fontFamily: "monospace",
          fontSize: 13,
        }}
        placeholder="输入内容..."
      />
    </div>
  );
}