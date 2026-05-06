import { useState, useEffect } from "react";
import { Modal, Upload, Select, message, Spin } from "antd";
import { InboxOutlined } from "@ant-design/icons";
import type { UploadProps } from "antd";
import { marketApi, type Category } from "../../../api/modules/market";

interface UploadSkillModalProps {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
  sourceId: string;
  userId: string;
  userName: string;
  bbkId: string;
}

const { Dragger } = Upload;

export default function UploadSkillModal({
  open,
  onClose,
  onSuccess,
  sourceId,
  userId,
  userName,
  bbkId,
}: UploadSkillModalProps) {
  const [categories, setCategories] = useState<Category[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<number | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [loadingCategories, setLoadingCategories] = useState(false);

  const loadCategories = async () => {
    setLoadingCategories(true);
    try {
      const data = await marketApi.listCategories(sourceId);
      setCategories(data);
      if (data.length > 0) {
        setSelectedCategory(data[0].id);
      }
    } catch (err) {
      console.error("Failed to load categories:", err);
    } finally {
      setLoadingCategories(false);
    }
  };

  useEffect(() => {
    if (open) {
      loadCategories();
      setFile(null);
      setSelectedCategory(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const handleUpload = async () => {
    if (!file) {
      message.error("请选择 zip 文件");
      return;
    }
    if (selectedCategory === null) {
      message.error("请选择技能分类");
      return;
    }

    setUploading(true);
    try {
      const result = await marketApi.uploadSkillToWorkspace(
        sourceId,
        userId,
        userName,
        bbkId,
        file,
        {
          enable: true,
          overwrite: false,
          category_id: selectedCategory,
        }
      );
      message.success(`上传成功，导入 ${result.count} 个技能`);
      onSuccess();
      onClose();
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "上传失败";
      message.error(errorMsg);
    } finally {
      setUploading(false);
    }
  };

  const uploadProps: UploadProps = {
    accept: ".zip",
    showUploadList: false,
    beforeUpload: (file) => {
      const isZip = file.name.toLowerCase().endsWith(".zip");
      if (!isZip) {
        message.error("仅支持 .zip 文件");
        return false;
      }
      setFile(file);
      return false;
    },
    onRemove: () => setFile(null),
    fileList: file ? [file as any] : [],
  };

  return (
    <Modal
      title="上传技能到市场"
      open={open}
      onCancel={onClose}
      onOk={handleUpload}
      okText="上传"
      cancelText="取消"
      okButtonProps={{
        loading: uploading,
        disabled: !file || selectedCategory === null,
      }}
      destroyOnClose
    >
      <div style={{ marginBottom: 16 }}>
        <Dragger {...uploadProps} style={{ marginBottom: 16 }}>
          <p className="ant-upload-drag-icon">
            <InboxOutlined />
          </p>
          <p className="ant-upload-text">拖拽 .zip 文件到此处</p>
          <p className="ant-upload-hint">或点击选择文件（需包含 SKILL.md）</p>
        </Dragger>
        {file && (
          <p style={{ color: "#52c41a", marginTop: 8 }}>
            已选择: {file.name}
          </p>
        )}
      </div>

      <div style={{ marginBottom: 16 }}>
        <label style={{ display: "block", marginBottom: 8 }}>
          技能分类 <span style={{ color: "#ff4d4f" }}>*</span>
        </label>
        {loadingCategories ? (
          <Spin size="small" />
        ) : (
          <Select
            style={{ width: "100%" }}
            value={selectedCategory}
            onChange={setSelectedCategory}
            placeholder="选择分类"
            options={categories.map((c) => ({ label: c.name, value: c.id }))}
          />
        )}
      </div>

      <p style={{ color: "#8c8c8c", fontSize: 12 }}>
        提示：技能名称和描述将从 zip 包中的 SKILL.md frontmatter 自动解析
      </p>
    </Modal>
  );
}
