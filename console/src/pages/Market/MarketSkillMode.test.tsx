import React from "react";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MarketSkills } from "./MarketSkills";

const mocks = vi.hoisted(() => ({
  useMarket: vi.fn(),
  marketMcpApi: {
    listMarketMCP: vi.fn(),
    getMarketMCPDetail: vi.fn(),
    deleteMarketMCP: vi.fn(),
    testMarketMCP: vi.fn(),
    updateMarketMCPMetadata: vi.fn(),
  },
}));

vi.mock("./useMarket", () => ({
  useMarket: mocks.useMarket,
}));

vi.mock("../../api/modules/marketMcp", () => ({
  marketMcpApi: mocks.marketMcpApi,
}));

vi.mock("./SkillCard", () => ({
  SkillCard: () => <div>skill-card</div>,
}));

vi.mock("./SkillDetailDrawer", () => ({
  SkillDetailDrawer: () => <div data-testid="skill-detail-panel">skill detail</div>,
}));

vi.mock("./DistributeTargetModal", () => ({
  DistributeTargetModal: () => null,
}));

vi.mock("./components/UploadSkillModal", () => ({
  default: () => null,
}));

vi.mock("./MCPCard", () => ({
  MCPCard: () => null,
}));

vi.mock("./MCPDetailDrawer", () => ({
  MCPDetailDrawer: () => null,
}));

vi.mock("./MCPUploadModal", () => ({
  MCPUploadModal: () => null,
}));

vi.mock("./MCPEditModal", () => ({
  MCPEditModal: () => null,
}));

describe("MarketSkills skill detail mode", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.useMarket.mockReturnValue({
      categories: [],
      skills: [],
      loading: false,
      selectedCategory: null,
      setSelectedCategory: vi.fn(),
      selectedSkill: {
        item_id: "skill-1",
        name: "预览技能",
        description: "说明",
        version: "1.0.0",
        creator_id: "u1",
        creator_name: "张三",
        category_id: 1,
        bbk_ids: [],
        status: "active",
        created_at: "2026-05-11T10:00:00Z",
        updated_at: "2026-05-11T10:00:00Z",
        call_count: 12,
        user_count: 3,
        user_stats: [],
      },
      detailDrawerOpen: true,
      setDetailDrawerOpen: vi.fn(),
      publishModalOpen: false,
      setPublishModalOpen: vi.fn(),
      refreshCategories: vi.fn(),
      refreshSkills: vi.fn(),
      openSkillDetail: vi.fn(),
    });
  });

  it("renders in-page skill detail mode with back action", () => {
    render(
      <MarketSkills
        sourceId="src_a"
        isManager={false}
      />,
    );

    expect(screen.getByText("返回列表")).toBeInTheDocument();
    expect(screen.getByTestId("skill-detail-panel")).toBeInTheDocument();
    expect(
      screen.queryByPlaceholderText("搜索技能名称、描述…"),
    ).not.toBeInTheDocument();
  });
});

