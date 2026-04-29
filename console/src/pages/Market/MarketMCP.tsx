import { Empty, Typography } from "antd";

const { Title } = Typography;

export function MarketMCP() {
  return (
    <div style={{ padding: 24, textAlign: "center" }}>
      <Title level={4}>MCP 市场</Title>
      <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="功能开发中，敬请期待" />
    </div>
  );
}