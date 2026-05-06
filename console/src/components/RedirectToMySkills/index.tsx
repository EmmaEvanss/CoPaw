// console/src/components/RedirectToMySkills/index.tsx
import { Button, Space, Typography } from "antd";
import { FolderOutlined, RightOutlined } from "@ant-design/icons";
import { useTranslation } from "react-i18next";

const { Text, Title } = Typography;

interface RedirectToMySkillsProps {
  feature: "create" | "edit" | "delete" | "enable-disable" | "upload";
}

export function RedirectToMySkills({ feature }: RedirectToMySkillsProps) {
  const { t } = useTranslation();

  const featureMessages: Record<string, { title: string; description: string }> = {
    create: {
      title: t("skills.redirectCreateTitle", "创建技能"),
      description: t("skills.redirectCreateDesc", "技能创建功能已迁移到「我的技能」页面"),
    },
    edit: {
      title: t("skills.redirectEditTitle", "编辑技能"),
      description: t("skills.redirectEditDesc", "技能编辑功能已迁移到「我的技能」页面"),
    },
    delete: {
      title: t("skills.redirectDeleteTitle", "删除技能"),
      description: t("skills.redirectDeleteDesc", "技能删除功能已迁移到「我的技能」页面"),
    },
    "enable-disable": {
      title: t("skills.redirectToggleTitle", "启用/禁用技能"),
      description: t("skills.redirectToggleDesc", "技能启用/禁用功能已迁移到「我的技能」页面"),
    },
    upload: {
      title: t("skills.redirectUploadTitle", "上传技能"),
      description: t("skills.redirectUploadDesc", "技能上传功能已迁移到「我的技能」页面"),
    },
  };

  const { title, description } = featureMessages[feature] || featureMessages.create;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        height: "100%",
        padding: 48,
        textAlign: "center",
      }}
    >
      <FolderOutlined style={{ fontSize: 48, color: "#1890ff", marginBottom: 24 }} />
      <Title level={4} style={{ marginBottom: 8 }}>
        {title}
      </Title>
      <Text type="secondary" style={{ marginBottom: 24 }}>
        {description}
      </Text>
      <Space>
        <Button type="primary" icon={<RightOutlined />} href="/my-skills">
          {t("skills.goToMySkills", "前往我的技能")}
        </Button>
      </Space>
    </div>
  );
}

export default RedirectToMySkills;
