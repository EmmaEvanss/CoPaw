import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import FeaturedCases from "./index";
import { featuredCasesApi } from "@/api/modules/featuredCases";

vi.mock("@/api/modules/featuredCases", () => ({
  featuredCasesApi: {
    listCases: vi.fn(),
  },
}));

const mockedListCases = vi.mocked(featuredCasesApi.listCases);

function createCase(index: number) {
  return {
    id: index,
    label: `案例${index}`,
    value: `内容${index}`,
    sort_order: index,
  };
}

describe("FeaturedCases", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows five cases first and expands remaining cases", async () => {
    mockedListCases.mockResolvedValue(
      Array.from({ length: 6 }, (_, index) => createCase(index + 1)),
    );

    render(<FeaturedCases />);

    await waitFor(() => {
      expect(screen.getByText("案例5")).toBeInTheDocument();
    });
    expect(screen.queryByText("案例6")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /查看更多/ }));

    expect(screen.getByText("案例6")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /收起/ })).toBeInTheDocument();
  });
});
