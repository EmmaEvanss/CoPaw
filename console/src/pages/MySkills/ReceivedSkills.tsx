import { List, Typography, Tag, Button, Space } from "antd";
import { SyncOutlined } from "@ant-design/icons";
import { MySkill } from "../../api/modules/mySkills";

const { Text } = Typography;

interface ReceivedSkillsProps {
  skills: MySkill[];
  onUpdate?: (skill: MySkill) => void;
}

export function ReceivedSkills({ skills, onUpdate }: ReceivedSkillsProps) {
  return (
    <List
      dataSource={skills}
      renderItem={(skill) => (
        <List.Item
          actions={[
            skill.has_update && onUpdate && (
              <Button type="link" icon={<SyncOutlined />} onClick={() => onUpdate(skill)}>
                更新
              </Button>
            ),
          ].filter(Boolean)}
        >
          <List.Item.Meta
            title={
              <Space>
                <Text strong>{skill.skill_name}</Text>
                {skill.received_version && <Tag color="green">v{skill.received_version}</Tag>}
                {skill.has_update && <Tag color="orange">有更新</Tag>}
              </Space>
            }
            description={
              <Space direction="vertical" size={0}>
                <Text type="secondary">{skill.description || "暂无描述"}</Text>
                {skill.distributed_by && (
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    分发人: {skill.distributed_by}
                  </Text>
                )}
              </Space>
            }
          />
        </List.Item>
      )}
    />
  );
}
