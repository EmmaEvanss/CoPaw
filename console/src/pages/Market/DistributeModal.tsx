import { Modal, Form, Radio, Select, Button } from "antd";
import { useState } from "react";
import { marketApi, DistributeRequest } from "../../api/modules/market";
import { MarketSkill } from "../../api/modules/market";
import { BBK_ID_MAP } from "../../constants/bbk";

interface DistributeModalProps {
  open: boolean;
  skill: MarketSkill | null;
  sourceId: string;
  userId: string;
  userName: string;
  onClose: () => void;
  onSuccess: () => void;
}

export function DistributeModal({
  open,
  skill,
  sourceId,
  userId,
  userName,
  onClose,
  onSuccess,
}: DistributeModalProps) {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [targetType, setTargetType] = useState<"all" | "bbk_id" | "user_id">("all");

  const handleSubmit = async () => {
    if (!skill) return;
    try {
      const values = await form.validateFields();
      setLoading(true);
      const payload: DistributeRequest = {
        target_type: targetType,
        target_values: targetType === "all" ? [] : values.target_values || [],
      };
      await marketApi.distributeSkill(sourceId, skill.item_id, userId, userName, payload);
      onSuccess();
      onClose();
    } catch (err) {
      console.error("Distribute failed:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      open={open}
      onCancel={onClose}
      title={`分发「${skill?.name || ""}」`}
      footer={[
        <Button key="cancel" onClick={onClose}>
          取消
        </Button>,
        <Button key="submit" type="primary" loading={loading} onClick={handleSubmit}>
          分发
        </Button>,
      ]}
    >
      <Form form={form} layout="vertical">
        <Form.Item label="分发目标">
          <Radio.Group value={targetType} onChange={(e) => setTargetType(e.target.value)}>
            <Radio value="all">全员</Radio>
            <Radio value="bbk_id">按机构</Radio>
            <Radio value="user_id">按用户</Radio>
          </Radio.Group>
        </Form.Item>
        {targetType === "bbk_id" && (
          <Form.Item name="target_values" label="选择机构">
            <Select mode="multiple" placeholder="选择机构" options={BBK_ID_MAP} />
          </Form.Item>
        )}
        {targetType === "user_id" && (
          <Form.Item name="target_values" label="用户ID">
            <Select mode="tags" placeholder="输入用户ID，回车添加" />
          </Form.Item>
        )}
      </Form>
    </Modal>
  );
}