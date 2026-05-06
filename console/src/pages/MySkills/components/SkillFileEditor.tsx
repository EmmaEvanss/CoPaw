import { Input, Button, Space } from "antd";
import { SaveOutlined, CloseOutlined } from "@ant-design/icons";

const { TextArea } = Input;

interface Props {
  content: string;
  fileType: string;
  onChange: (content: string) => void;
  onSave: () => void;
  onCancel: () => void;
  saving: boolean;
}

export function SkillFileEditor({
  content,
  fileType,
  onChange,
  onSave,
  onCancel,
  saving,
}: Props) {
  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <div
        style={{
          marginBottom: 12,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <span style={{ fontSize: 12, color: "#8c8c8c" }}>
          编辑模式 -{" "}
          {fileType === "markdown"
            ? "Markdown"
            : fileType === "json"
              ? "JSON"
              : "文本"}
        </span>
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