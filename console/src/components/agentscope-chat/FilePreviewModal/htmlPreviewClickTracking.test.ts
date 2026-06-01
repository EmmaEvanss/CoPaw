import { describe, expect, it, vi } from "vitest";
import {
  attachHtmlPreviewClickTracker,
  buildHtmlPreviewClickPayload,
} from "./htmlPreviewClickTracking";

function createDocument(html: string) {
  const doc = document.implementation.createHTMLDocument("preview");
  doc.body.innerHTML = html;
  return doc;
}

describe("htmlPreviewClickTracking", () => {
  it("prefers data-track-id and data-track-name for click payload", () => {
    const doc = createDocument(
      '<button data-track-id="follow" data-track-name="立即跟进">跟进客户</button>',
    );
    const button = doc.querySelector("button") as HTMLElement;

    const payload = buildHtmlPreviewClickPayload(
      button,
      {
        cronTaskId: "task-1",
        cronTaskName: "存款到期提醒",
        fileUrl: "https://example.com/a.html",
        fileName: "a.html",
      },
      new Date("2026-05-30T10:00:00.000Z"),
    );

    expect(payload).toMatchObject({
      cron_task_id: "task-1",
      cron_task_name: "存款到期提醒",
      file_url: "https://example.com/a.html",
      file_name: "a.html",
      button_id: "follow",
      button_name: "立即跟进",
      button_text: "跟进客户",
      clicked_at: "2026-05-30T10:00:00.000Z",
    });
  });

  it("falls back to id, name and text when tracking attributes are absent", () => {
    const doc = createDocument('<button name="call-customer">预约电话</button>');
    const button = doc.querySelector("button") as HTMLElement;

    const payload = buildHtmlPreviewClickPayload(button, {
      fileUrl: "https://example.com/a.html",
      fileName: "a.html",
    });

    expect(payload?.button_id).toBe("call-customer");
    expect(payload?.button_name).toBe("call-customer");
    expect(payload?.button_text).toBe("预约电话");
  });

  it("prefers structured customer fields from the clicked table row", () => {
    const doc = createDocument(`
      <table>
        <tbody>
          <tr data-customer-id="CUST-001" data-customer-name="祝话" data-customer-product="定存243M">
            <td>祝话</td>
            <td>定存243M</td>
            <td><a data-track-id="insight">洞察页面</a></td>
          </tr>
        </tbody>
      </table>
    `);
    const link = doc.querySelector("a") as HTMLElement;

    const payload = buildHtmlPreviewClickPayload(link, {
      fileUrl: "https://example.com/a.html",
      fileName: "a.html",
    });

    expect(payload?.customer_info).toEqual({
      customer_id: "CUST-001",
      name: "祝话",
    });
  });

  it("only keeps customer identity when falling back to table headers", () => {
    const doc = createDocument(`
      <table>
        <thead>
          <tr>
            <th>序号</th>
            <th>客户姓名</th>
            <th>到期产品</th>
            <th>到期金额</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>3</td>
            <td>祝话</td>
            <td>定存243M</td>
            <td>18.00万元</td>
            <td><a class="link-btn phone">电话访问</a></td>
          </tr>
        </tbody>
      </table>
    `);
    const link = doc.querySelector("a") as HTMLElement;

    const payload = buildHtmlPreviewClickPayload(link, {
      fileUrl: "https://example.com/a.html",
      fileName: "a.html",
    });

    expect(payload?.customer_info).toEqual({
      "客户姓名": "祝话",
    });
  });

  it("listens to iframe clicks without blocking rejected reports", async () => {
    const iframe = document.createElement("iframe");
    document.body.appendChild(iframe);
    const doc = iframe.contentDocument!;
    doc.body.innerHTML =
      '<div><button id="follow"><span>立即跟进</span></button></div>';
    const reporter = vi.fn(() => Promise.reject(new Error("network error")));

    const cleanup = attachHtmlPreviewClickTracker({
      iframe,
      metadata: {
        fileUrl: "https://example.com/a.html",
        fileName: "a.html",
      },
      reporter,
    });

    const span = doc.querySelector("span") as HTMLElement;
    span.dispatchEvent(new doc.defaultView!.MouseEvent("click", { bubbles: true }));
    await Promise.resolve();

    expect(reporter).toHaveBeenCalledTimes(1);
    expect(reporter.mock.calls[0][0]).toMatchObject({
      button_id: "follow",
      button_name: "立即跟进",
      button_text: "立即跟进",
    });

    cleanup();
    document.body.removeChild(iframe);
  });

  it("does not throw when reporter fails synchronously", () => {
    const iframe = document.createElement("iframe");
    document.body.appendChild(iframe);
    const doc = iframe.contentDocument!;
    doc.body.innerHTML = '<button id="follow">立即跟进</button>';
    const reporter = vi.fn(() => {
      throw new Error("sync error");
    });

    const cleanup = attachHtmlPreviewClickTracker({
      iframe,
      metadata: {
        fileUrl: "https://example.com/a.html",
        fileName: "a.html",
      },
      reporter,
    });

    const button = doc.querySelector("button") as HTMLElement;
    expect(() =>
      button.dispatchEvent(
        new doc.defaultView!.MouseEvent("click", { bubbles: true }),
      ),
    ).not.toThrow();
    expect(reporter).toHaveBeenCalledTimes(1);

    cleanup();
    document.body.removeChild(iframe);
  });
});
