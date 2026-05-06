/**
 * 发布 MCP 到市场弹窗
 */
import { useState } from "react";
import { Modal, Form, Select, Button, message, Typography, Alert } from "antd";
import { RocketOutlined } from "@ant-design/icons";
import { myMcpApi } from "../../api/modules/myMcp";
import { BBK_ID_MAP } from "../../constants/bbk";

const { Text } = Typography;

interface PublishMCPModalProps {
  open: boolean;
  sourceId: string;
  userId: string;
  userName: string;
  clientKey: string;
  clientName: string;
  onClose: () => void;
  onSuccess: () => void;
}

export function PublishMCPModal({
  open,
  sourceId,
  userId,
  userName,
  clientKey,
  clientName,
  onClose,
  onSuccess,
}: PublishMCPModalProps) {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    if (!clientKey) {
      message.warning("未找到可上架的 MCP");
      return;
    }

    try {
      const values = await form.validateFields();
      setLoading(true);

      await myMcpApi.publishSingleToMarket(sourceId, userId, userName, clientKey, {
        bbk_ids: values.bbk_ids,
      });
      message.success("上架成功");
      onSuccess();
    } catch (err) {
      console.error("上架失败:", err);
      const errorMessage =
        err instanceof Error && err.message ? err.message : "上架失败";
      message.error(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      open={open}
      onCancel={onClose}
      title={<><RocketOutlined /> 发布到市场</>}
      width={500}
      footer={[
        <Button key="cancel" onClick={onClose}>
          关闭
        </Button>,
        <Button key="submit" type="primary" loading={loading} onClick={handleSubmit}>
          发布
        </Button>,
      ]}
    >
      <Alert
        type="info"
        message="将当前 MCP 上架到应用市场"
        style={{ marginBottom: 16 }}
        showIcon
      />

      <div style={{ marginBottom: 16 }}>
        <Text type="secondary">当前 MCP</Text>
        <div style={{ marginTop: 6, fontWeight: 500 }}>
          {clientName || clientKey}
        </div>
      </div>

      <Form form={form} layout="vertical">
        <Form.Item name="bbk_ids" label="可见机构">
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
