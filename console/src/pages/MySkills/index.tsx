import { useEffect, useState } from "react";
import { Typography, Tree, Card, Spin } from "antd";
import { CreatedSkills } from "./CreatedSkills";
import { ReceivedSkills } from "./ReceivedSkills";
import { useMySkills } from "./useMySkills";
import { useIframeStore } from "../../stores/iframeStore";
import { getUserId } from "../../utils/identity";
import { DEFAULT_SOURCE_ID } from "../../constants/identity";

const { Title } = Typography;

type TabKey = "created" | "received";

export default function MySkillsPage() {
  const sourceId = useIframeStore((state) => state.source) || DEFAULT_SOURCE_ID;
  const userId = getUserId();
  const { createdSkills, receivedSkills, loading, refresh } = useMySkills(sourceId, userId);
  const [selectedTab, setSelectedTab] = useState<TabKey>("created");

  useEffect(() => {
    refresh();
  }, [refresh]);

  const treeData = [
    { key: "created", title: `我创建的 (${createdSkills.length})` },
    { key: "received", title: `我接收的 (${receivedSkills.length})` },
  ];

  return (
    <div style={{ display: "flex", height: "100%" }}>
      <div style={{ width: 200, borderRight: "1px solid #f0f0f0", padding: 16 }}>
        <Tree
          treeData={treeData}
          selectedKeys={[selectedTab]}
          onSelect={(keys) => setSelectedTab(keys[0] as TabKey)}
        />
      </div>
      <div style={{ flex: 1, padding: 16, overflow: "auto" }}>
        <Card>
          {loading ? (
            <Spin />
          ) : selectedTab === "created" ? (
            <>
              <Title level={4}>我创建的技能</Title>
              <CreatedSkills skills={createdSkills} />
            </>
          ) : (
            <>
              <Title level={4}>我接收的技能</Title>
              <ReceivedSkills skills={receivedSkills} />
            </>
          )}
        </Card>
      </div>
    </div>
  );
}
