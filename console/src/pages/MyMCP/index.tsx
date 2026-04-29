import { Empty, Typography } from "antd";

const { Title } = Typography;

export default function MyMCPPage() {
  return (
    <div style={{ padding: 24 }}>
      <Title level={4}>我的 MCP</Title>
      <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="功能开发中，敬请期待" />
    </div>
  );
}
