/**
 * MCP 市场元数据编辑弹窗。
 *
 * 说明：
 * - 只允许编辑展示元数据
 * - 不允许在此处修改连接器配置或重新上传文件
 */
import { useEffect, useState } from "react";
import { Alert, Button, Form, Input, Modal, Select, message } from "antd";
import { marketMcpApi } from "../../api/modules/marketMcp";
import { BBK_ID_MAP } from "../../constants/bbk";
import type { MarketMCPDetail } from "../../api/types";

interface MCPEditModalProps {
  open: boolean;
  mcp: MarketMCPDetail | null;
  sourceId: string;
  userId: string;
  userName: string;
  onClose: () => void;
  onSuccess: (detail: MarketMCPDetail) => void;
}

interface MCPMetadataEditFormValues {
  chinese_name?: string;
  description?: string;
  guidance?: string;
  bbk_ids?: string[];
}

export function MCPEditModal({
  open,
  mcp,
  sourceId,
  userId,
  userName,
  onClose,
  onSuccess,
}: MCPEditModalProps) {
  const [form] = Form.useForm<MCPMetadataEditFormValues>();
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open || !mcp) return;
    form.setFieldsValue({
      chinese_name: mcp.chinese_name || "",
      description: mcp.description || "",
      guidance: mcp.guidance || "",
      bbk_ids: mcp.bbk_ids || [],
    });
  }, [form, mcp, open]);

  const handleClose = () => {
    form.resetFields();
    onClose();
  };

  const handleSubmit = async () => {
    if (!mcp) return;
    try {
      const values = await form.validateFields();
      setSubmitting(true);
      const detail = await marketMcpApi.updateMarketMCPMetadata(
        sourceId,
        mcp.item_id,
        userId,
        userName,
        {
          chinese_name: values.chinese_name || "",
          description: values.description || "",
          guidance: values.guidance || "",
          bbk_ids: values.bbk_ids || [],
        },
      );
      message.success("保存成功");
      form.resetFields();
      onSuccess(detail);
    } catch (error) {
      console.error("更新 MCP 市场元数据失败:", error);
      if (error instanceof Error) {
        message.error(error.message);
      } else {
        message.error("保存失败");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      open={open}
      title="编辑 MCP 信息"
      onCancel={handleClose}
      width={600}
      footer={[
        <Button key="cancel" onClick={handleClose}>
          取消
        </Button>,
        <Button
          key="submit"
          type="primary"
          loading={submitting}
          onClick={() => void handleSubmit()}
        >
          保存
        </Button>,
      ]}
    >
      <Alert
        type="info"
        showIcon
        message="仅支持修改展示信息；如需修改连接器配置，请使用“上传连接器”重新上传覆盖。"
        style={{ marginBottom: 16 }}
      />

      <Form form={form} layout="vertical">
        <Form.Item label="英文名称（只读）">
          <Input value={mcp?.name || ""} disabled />
        </Form.Item>
        <Form.Item label="中文名称（可选）" name="chinese_name">
          <Input placeholder="请输入中文名称（可选）" />
        </Form.Item>
        <Form.Item label="描述（可选）" name="description">
          <Input.TextArea rows={3} placeholder="请输入描述（可选）" />
        </Form.Item>
        <Form.Item label="使用指引（可选）" name="guidance">
          <Input.TextArea rows={4} placeholder="请输入使用指引（可选）" />
        </Form.Item>
        <Form.Item label="可见机构" name="bbk_ids">
          <Select
            mode="multiple"
            allowClear
            placeholder="不选择则全员可见"
            options={BBK_ID_MAP}
          />
        </Form.Item>
      </Form>
    </Modal>
  );
}
