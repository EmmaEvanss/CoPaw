import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import WelcomeCenterLayout from "./index";
import { chatApi } from "@/api/modules/chat";

vi.mock("@agentscope-ai/icons", () => ({
  SparkAttachmentLine: () => <span data-testid="attachment-icon" />,
}));

vi.mock("@agentscope-ai/design", () => ({
  IconButton: () => <button type="button">upload</button>,
}));

vi.mock("@/components/agentscope-chat", () => ({
  Attachments: ({ items }: { items: Array<{ name?: string }> }) => (
    <div>
      {items.map((item) => (
        <span key={item.name}>{item.name}</span>
      ))}
    </div>
  ),
}));

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock("@/api/modules/chat", () => ({
  chatApi: {
    uploadFile: vi.fn(),
    filePreviewUrl: vi.fn((filename: string) => `/preview/${filename}`),
  },
}));

vi.mock("../FeaturedCases", () => ({
  default: () => <div data-testid="featured-cases" />,
}));

vi.mock("../CaseDetailDrawer", () => ({
  default: () => null,
}));

vi.mock("@/api/modules/featuredCases", () => ({
  featuredCasesApi: {
    getCaseDetail: vi.fn(),
  },
}));

const mockedUploadFile = vi.mocked(chatApi.uploadFile);

describe("WelcomeCenterLayout", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedUploadFile.mockResolvedValue({
      url: "demo.txt",
      file_name: "demo.txt",
    });
  });

  it("handles files dispatched by the chat drag-and-drop bridge", async () => {
    const file = new File(["hello"], "demo.txt", { type: "text/plain" });

    render(<WelcomeCenterLayout greeting="你好" onSubmit={vi.fn()} />);

    document.dispatchEvent(
      new CustomEvent("pasteFile", {
        detail: { file },
      }),
    );

    expect(mockedUploadFile).toHaveBeenCalledWith(file);
    await waitFor(() => {
      expect(screen.getByText("demo.txt")).toBeInTheDocument();
    });
  });
});
