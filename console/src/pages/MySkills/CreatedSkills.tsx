import { List, Typography, Tag, Button, Space } from "antd";
import { EditOutlined, DeleteOutlined } from "@ant-design/icons";
import { MySkill } from "../../api/modules/mySkills";

const { Text } = Typography;

interface CreatedSkillsProps {
  skills: MySkill[];
  onEdit?: (skill: MySkill) => void;
  onDelete?: (skill: MySkill) => void;
}

export function CreatedSkills({ skills, onEdit, onDelete }: CreatedSkillsProps) {
  return (
    <List
      dataSource={skills}
      renderItem={(skill) => (
        <List.Item
          actions={[
            onEdit && (
              <Button type="link" icon={<EditOutlined />} onClick={() => onEdit(skill)}>
                编辑
              </Button>
            ),
            onDelete && (
              <Button type="link" danger icon={<DeleteOutlined />} onClick={() => onDelete(skill)}>
                删除
              </Button>
            ),
          ].filter(Boolean)}
        >
          <List.Item.Meta
            title={
              <Space>
                <Text strong>{skill.skill_name}</Text>
                {skill.version && <Tag>v{skill.version}</Tag>}
              </Space>
            }
            description={skill.description || "暂无描述"}
          />
        </List.Item>
      )}
    />
  );
}
