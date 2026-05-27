import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import DownloadFileCard from "./index";

vi.mock("@agentscope-ai/icons", () => ({
  SparkDownloadLine: () => <span data-testid="download-icon" />,
}));

vi.mock("../FilePreviewModal", () => ({
  default: (props: { open: boolean; fileName: string }) =>
    props.open ? (
      <div data-testid="file-preview-modal">{props.fileName}</div>
    ) : null,
}));

afterEach(() => {
  cleanup();
});

describe("DownloadFileCard", () => {
  it("自动打开带 auto-preview 标记的 HTML 预览", async () => {
    render(
      <DownloadFileCard
        url="https://example.test/static/report[auto-preview]-1.html"
        fileName="report[auto-preview]-1.html"
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("file-preview-modal")).toHaveTextContent(
        "report[auto-preview]-1.html",
      );
    });
  });

  it("自动打开带存款到期完整客户名单关键词的 HTML 预览", async () => {
    render(
      <DownloadFileCard
        url="https://example.test/static/report-1.html"
        fileName="存款到期完整客户名单-2026-05-29.html"
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("file-preview-modal")).toHaveTextContent(
        "存款到期完整客户名单-2026-05-29.html",
      );
    });
  });

  it("普通 HTML 链接不自动打开预览", () => {
    render(
      <DownloadFileCard
        url="https://example.test/static/report.html"
        fileName="report.html"
      />,
    );

    expect(screen.queryByTestId("file-preview-modal")).not.toBeInTheDocument();
  });

  it("仍然支持用户点击卡片后打开预览", () => {
    render(
      <DownloadFileCard
        url="https://example.test/static/report.html"
        fileName="report.html"
      />,
    );

    fireEvent.click(screen.getByRole("button"));

    expect(screen.getByTestId("file-preview-modal")).toHaveTextContent(
      "report.html",
    );
  });
});
