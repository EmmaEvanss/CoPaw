import React from "react";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MarketSkills } from "./MarketSkills";

const mocks = vi.hoisted(() => ({
  marketMcpApi: {
    listMarketMCP: vi.fn(),
    getMarketMCPDetail: vi.fn(),
    deleteMarketMCP: vi.fn(),
    testMarketMCP: vi.fn(),
    updateMarketMCPMetadata: vi.fn(),
  },
  useMarket: vi.fn(),
}));

vi.mock("./useMarket", () => ({
  useMarket: mocks.useMarket,
}));

vi.mock("../../api/modules/marketMcp", () => ({
  marketMcpApi: mocks.marketMcpApi,
}));

vi.mock("./SkillCard", () => ({
  SkillCard: () => <div data-testid="skill-card">skill</div>,
}));

vi.mock("./SkillDetailDrawer", () => ({
  SkillDetailDrawer: () => null,
}));

vi.mock("./PublishModal", () => ({
  PublishModal: () => null,
}));

vi.mock("./DistributeModal", () => ({
  DistributeModal: () => null,
}));

const marketMcpList = [
  {
    item_id: "mcp-1",
    client_key: "weather-tools",
    name: "Weather Tools",
    call_count: 120,
    user_count: 18,
  },
];

const marketMcpDetail = {
  ...marketMcpList[0],
  creator_name: "张三",
  created_at: "2026-05-02 14:21:35",
  updated_at: "2026-05-02 16:08:11",
  config: {
    name: "Weather Tools",
    description: "网络天气查询连接器",
    transport: "streamable_http" as const,
    url: "https://mcp.example.com",
    headers: { Authorization: "******" },
    command: "",
    args: [],
    env: {},
    cwd: "",
  },
  user_stats: [
    { user_id: "u001", user_name: "张三", call_count: 24 },
  ],
};

describe("MarketSkills MCP tab", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    vi.clearAllMocks();
    container = document.createElement("div");
    document.body.innerHTML = "";
    document.body.appendChild(container);
    root = createRoot(container);
    mocks.useMarket.mockReturnValue({
      categories: [],
      skills: [],
      loading: false,
      selectedCategory: null,
      setSelectedCategory: vi.fn(),
      selectedSkill: null,
      detailDrawerOpen: false,
      setDetailDrawerOpen: vi.fn(),
      publishModalOpen: false,
      setPublishModalOpen: vi.fn(),
      distributeModalOpen: false,
      setDistributeModalOpen: vi.fn(),
      distributeTargetSkill: null,
      refreshCategories: vi.fn(),
      refreshSkills: vi.fn(),
      openSkillDetail: vi.fn(),
      openDistributeModal: vi.fn(),
    });
    mocks.marketMcpApi.listMarketMCP.mockResolvedValue(marketMcpList);
    mocks.marketMcpApi.getMarketMCPDetail.mockResolvedValue(marketMcpDetail);
    mocks.marketMcpApi.deleteMarketMCP.mockResolvedValue(undefined);
    mocks.marketMcpApi.testMarketMCP.mockResolvedValue({
      success: true,
      tools: [{ name: "get_weather", description: "天气查询" }],
    });
    mocks.marketMcpApi.updateMarketMCPMetadata.mockResolvedValue(marketMcpDetail);
  });

  function renderComponent(isManager = true) {
    act(() => {
      root.render(
        <MarketSkills
          sourceId=""
          isManager={isManager}
        />,
      );
    });
  }

  async function flush() {
    await act(async () => {
      await Promise.resolve();
    });
  }

  it("renders MCP cards with detail, distribute and delete actions in list mode", async () => {
    renderComponent();

    const mcpTab = Array.from(container.querySelectorAll("span")).find(
      (node) => node.textContent === "MCP",
    );
    act(() => {
      mcpTab?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    await flush();

    expect(container.textContent).toContain("Weather Tools");
    expect(
      Array.from(container.querySelectorAll("button")).some(
        (node) => node.textContent?.includes("详情"),
      ),
    ).toBe(true);
    expect(
      Array.from(container.querySelectorAll("button")).some(
        (node) => node.textContent?.includes("分发"),
      ),
    ).toBe(true);
    expect(
      Array.from(container.querySelectorAll("button")).some(
        (node) => node.textContent?.includes("删除"),
      ),
    ).toBe(true);
  });

  it("shows edit action for manager in MCP list mode", async () => {
    renderComponent(true);

    const mcpTab = Array.from(container.querySelectorAll("span")).find(
      (node) => node.textContent === "MCP",
    );
    act(() => {
      mcpTab?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    await flush();

    expect(
      Array.from(container.querySelectorAll("button")).some(
        (node) => node.textContent?.includes("编辑"),
      ),
    ).toBe(true);
  });

  it("hides edit action for non-manager in MCP list mode", async () => {
    renderComponent(false);

    const mcpTab = Array.from(container.querySelectorAll("span")).find(
      (node) => node.textContent === "MCP",
    );
    act(() => {
      mcpTab?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    await flush();

    expect(
      Array.from(container.querySelectorAll("button")).some(
        (node) => node.textContent?.includes("编辑"),
      ),
    ).toBe(false);
  });

  it("switches from list mode to in-page detail mode when opening an MCP", async () => {
    renderComponent();

    const mcpTab = Array.from(container.querySelectorAll("span")).find(
      (node) => node.textContent === "MCP",
    );
    act(() => {
      mcpTab?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    await flush();

    const detailButton = Array.from(container.querySelectorAll("button")).find(
      (node) => node.textContent?.includes("详情"),
    );
    act(() => {
      detailButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    await flush();

    expect(container.textContent).toContain("返回列表");
    expect(container.textContent).toContain("测试连接");
    const searchInput = container.querySelector("input[placeholder='搜索 MCP 名称']");
    expect(searchInput).toBeNull();
  });

  it("shows edit action in MCP detail mode for manager", async () => {
    renderComponent(true);

    const mcpTab = Array.from(container.querySelectorAll("span")).find(
      (node) => node.textContent === "MCP",
    );
    act(() => {
      mcpTab?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    await flush();

    const detailButton = Array.from(container.querySelectorAll("button")).find(
      (node) => node.textContent?.includes("详情"),
    );
    act(() => {
      detailButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    await flush();

    expect(
      Array.from(container.querySelectorAll("button")).some(
        (node) => node.textContent?.includes("编辑"),
      ),
    ).toBe(true);
  });
});
