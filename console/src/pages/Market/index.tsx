import { MarketSkills } from "./MarketSkills";
import { useIframeStore } from "../../stores/iframeStore";
import { getUserId } from "../../utils/identity";
import { DEFAULT_SOURCE_ID, DEFAULT_BBK_ID } from "../../constants/identity";

export default function MarketPage() {
  const sourceId = useIframeStore((state) => state.source) || DEFAULT_SOURCE_ID;
  const bbkId = useIframeStore((state) => state.bbk) || DEFAULT_BBK_ID;
  const userId = getUserId();
  const userName = useIframeStore((state) => state.clawName) || "Unknown";
  const isManager = useIframeStore((state) => state.manager);

  return (
    <MarketSkills
      sourceId={sourceId}
      bbkId={bbkId}
      userId={userId}
      userName={userName}
      isManager={isManager}
    />
  );
}
