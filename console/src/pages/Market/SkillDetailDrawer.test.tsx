import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SkillDetailDrawer } from "./SkillDetailDrawer";

const mocks = vi.hoisted(() => ({
  readSkillFile: vi.fn(),
}));

vi.mock("../../api/modules/market", async () => {
  const actual = await vi.importActual<typeof import("../../api/modules/market")>(
    "../../api/modules/market",
  );
  return {
    ...actual,
    marketApi: {
      ...actual.marketApi,
      readSkillFile: mocks.readSkillFile,
    },
  };
});

describe("SkillDetailDrawer", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.readSkillFile.mockImplementation(
      async (_sourceId: string, _itemId: string, filePath: string) => {
        if (filePath === "SKILL.md") {
          return {
            content:
              "---\nname: preview_skill\ncategory: 数据分析\n---\n# 使用说明\n\n这里是技能文档。",
            file_type: "markdown",
          };
        }
        return {
          content: '{\n  "name": "preview_skill"\n}',
          file_type: "json",
        };
      },
    );
  });

  it("renders reference-style preview layout and loads files", async () => {
    const onDistribute = vi.fn();

    render(
      <SkillDetailDrawer
        open
        skill={{
          item_id: "skill-1",
          name: "preview_skill",
          chinese_name: "预览技能",
          description: "这是一个预览技能",
          version: "1.0.0",
          creator_id: "u1",
          creator_name: "张三",
          category_id: 1,
          bbk_ids: [],
          status: "active",
          created_at: "2026-05-11T10:00:00Z",
          updated_at: "2026-05-11T10:00:00Z",
          call_count: 42,
          user_count: 8,
          user_stats: [
            {
              user_id: "u100",
              user_name: "李四",
              call_count: 12,
            },
          ],
        }}
        onClose={vi.fn()}
        isManager
        onDistribute={onDistribute}
        sourceId="src_a"
        categoryName="效率工具"
      />,
    );

    await waitFor(() => {
      expect(mocks.readSkillFile).toHaveBeenCalledWith(
        "src_a",
        "skill-1",
        "SKILL.md",
      );
    });

    expect(screen.getAllByText("预览技能").length).toBeGreaterThan(0);
    expect(screen.getByText("使用用户明细")).toBeInTheDocument();
    expect(screen.getAllByText("调用次数").length).toBeGreaterThan(0);
    expect(screen.getByText("使用用户数")).toBeInTheDocument();
    expect(screen.getByText("效率工具")).toBeInTheDocument();
    expect(screen.queryByText("分类 #1")).not.toBeInTheDocument();
    expect(screen.queryByText("SKILL.md")).not.toBeInTheDocument();
    expect(screen.queryByText("skill.json")).not.toBeInTheDocument();
    expect(screen.queryByText("只读")).not.toBeInTheDocument();
    expect(screen.getByText("李四")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "分发技能" })).toBeInTheDocument();
    expect(screen.queryByText("安装")).not.toBeInTheDocument();
    expect(screen.queryByText("卸载")).not.toBeInTheDocument();
    expect(await screen.findByText("使用说明")).toBeInTheDocument();
    expect(screen.getByTestId("skill-markdown-preview")).toBeInTheDocument();
    expect(screen.queryByText("name: preview_skill")).not.toBeInTheDocument();
    expect(screen.queryByText("category: 数据分析")).not.toBeInTheDocument();
    expect(screen.getByTestId("skill-markdown-preview").parentElement).toHaveStyle({
      width: "100%",
      padding: "12px",
    });
    expect(screen.getByTestId("skill-markdown-preview").parentElement?.parentElement).toHaveStyle({
      flex: "1 1 auto",
      width: "100%",
      padding: "12px",
    });

    fireEvent.click(screen.getByRole("button", { name: "分发技能" }));
    expect(onDistribute).toHaveBeenCalledTimes(1);
  });
});
