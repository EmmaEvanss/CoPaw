import type { HtmlPreviewClickEventPayload } from "@/api/types/htmlPreviewEvents";

export interface HtmlPreviewClickMetadata {
  cronTaskId?: string | null;
  cronTaskName?: string | null;
  fileUrl: string;
  fileName?: string | null;
}

export type HtmlPreviewClickReporter = (
  payload: HtmlPreviewClickEventPayload,
) => Promise<unknown> | unknown;

const CLICKABLE_SELECTOR = "button,a,[role='button'],[data-track-id]";
const CUSTOMER_DATA_PREFIX = "customer";
const CUSTOMER_INFO_DATA_KEY = "customerInfo";
const CUSTOMER_NAME_HEADER_PATTERN = /^(客户姓名|客户名称|姓名)$/;
const CUSTOMER_INFO_ALLOWED_KEYS = new Set([
  "customer_id",
  "customer_name",
  "name",
  "客户姓名",
  "客户名称",
  "姓名",
]);

function normalizeText(value: string | null | undefined, maxLength: number) {
  const normalized = value?.replace(/\s+/g, " ").trim() || "";
  return normalized ? normalized.slice(0, maxLength) : null;
}

function normalizeKey(value: string) {
  return value
    .replace(/([a-z0-9])([A-Z])/g, "$1_$2")
    .replace(/[\s-]+/g, "_")
    .toLowerCase();
}

function normalizeCustomerDatasetKey(key: string) {
  const rawKey = key.replace(CUSTOMER_DATA_PREFIX, "") || key;
  const normalizedKey = normalizeKey(rawKey);
  return normalizedKey === "id" ? "customer_id" : normalizedKey;
}

function getElementName(element: HTMLElement, buttonText: string | null) {
  return normalizeText(
    element.dataset.trackName ||
      element.getAttribute("aria-label") ||
      element.getAttribute("title") ||
      element.getAttribute("name") ||
      buttonText,
    255,
  );
}

function parseCustomerInfoJson(value: string | undefined) {
  if (!value) {
    return null;
  }
  try {
    const parsed = JSON.parse(value) as Record<string, unknown>;
    return Object.fromEntries(
      Object.entries(parsed)
        .map(([key, item]) => [
          normalizeKey(key),
          item == null ? null : normalizeText(String(item), 512),
        ])
        .filter(
          (entry): entry is [string, string] =>
            Boolean(entry[1]) && CUSTOMER_INFO_ALLOWED_KEYS.has(entry[0]),
        ),
    );
  } catch {
    return null;
  }
}

function getStructuredCustomerInfo(element: HTMLElement) {
  const candidate = element.closest<HTMLElement>(
    `[data-customer-info],tr,[data-customer-name]`,
  );
  if (!candidate) {
    return null;
  }

  const jsonInfo = parseCustomerInfoJson(candidate.dataset[CUSTOMER_INFO_DATA_KEY]);
  if (jsonInfo && Object.keys(jsonInfo).length > 0) {
    return jsonInfo;
  }

  const entries = Object.entries(candidate.dataset)
    .filter(
      ([key, value]) =>
        key !== CUSTOMER_INFO_DATA_KEY &&
        key.startsWith(CUSTOMER_DATA_PREFIX) &&
        CUSTOMER_INFO_ALLOWED_KEYS.has(normalizeCustomerDatasetKey(key)) &&
        Boolean(normalizeText(value, 512)),
    )
    .map(([key, value]) => [
      normalizeCustomerDatasetKey(key),
      normalizeText(value, 512),
    ])
    .filter((entry): entry is [string, string] => Boolean(entry[1]));

  return entries.length > 0 ? Object.fromEntries(entries) : null;
}

function getTableHeaders(row: HTMLTableRowElement) {
  const table = row.closest("table");
  const headerCells = table
    ? Array.from(table.querySelectorAll("thead th"))
    : [];
  const fallbackHeaderCells =
    headerCells.length > 0
      ? headerCells
      : Array.from(table?.querySelectorAll("tr:first-child th") || []);

  return fallbackHeaderCells.map((cell, index) => {
    const text = normalizeText(cell.textContent, 64);
    return text || `column_${index + 1}`;
  });
}

function getFallbackCustomerInfoFromRow(element: HTMLElement) {
  const row = element.closest("tr");
  if (!row || row.tagName !== "TR") {
    return null;
  }

  const headers = getTableHeaders(row);
  const cells = Array.from(row.children).filter((cell) =>
    ["TD", "TH"].includes(cell.tagName),
  );
  const entries = cells
    .map((cell, index) => {
      const header = headers[index] || `column_${index + 1}`;
      if (!CUSTOMER_NAME_HEADER_PATTERN.test(header)) {
        return null;
      }
      const value = normalizeText(cell.textContent, 512);
      return value ? [header, value] : null;
    })
    .filter((entry): entry is [string, string] => Boolean(entry));

  return entries.length > 0 ? Object.fromEntries(entries) : null;
}

function getCustomerInfo(element: HTMLElement) {
  return (
    getStructuredCustomerInfo(element) ||
    getFallbackCustomerInfoFromRow(element)
  );
}

export function buildHtmlPreviewClickPayload(
  element: HTMLElement,
  metadata: HtmlPreviewClickMetadata,
  clickedAt: Date = new Date(),
): HtmlPreviewClickEventPayload | null {
  const buttonText = normalizeText(element.textContent, 512);
  const buttonId = normalizeText(
    element.dataset.trackId ||
      element.id ||
      element.getAttribute("name") ||
      buttonText,
    255,
  );
  const buttonName = getElementName(element, buttonText);

  if (!buttonId && !buttonName && !buttonText) {
    return null;
  }

  return {
    cron_task_id: metadata.cronTaskId || null,
    cron_task_name: metadata.cronTaskName || null,
    file_url: metadata.fileUrl,
    file_name: metadata.fileName || null,
    button_id: buttonId,
    button_name: buttonName,
    button_text: buttonText,
    customer_info: getCustomerInfo(element),
    clicked_at: clickedAt.toISOString(),
  };
}

export function attachHtmlPreviewClickTracker(params: {
  iframe: HTMLIFrameElement;
  metadata: HtmlPreviewClickMetadata;
  reporter: HtmlPreviewClickReporter;
}): () => void {
  const doc = params.iframe.contentDocument;
  const view = doc?.defaultView;
  if (!doc || !view) {
    return () => {};
  }

  const handleClick = (event: MouseEvent) => {
    const target = event.target;
    if (!(target instanceof view.Element)) {
      return;
    }

    const element = target.closest(CLICKABLE_SELECTOR);
    if (!(element instanceof view.HTMLElement)) {
      return;
    }

    const payload = buildHtmlPreviewClickPayload(
      element,
      params.metadata,
    );
    if (!payload) {
      return;
    }

    try {
      void Promise.resolve(params.reporter(payload)).catch((error) => {
        console.warn("Failed to record HTML preview click:", error);
      });
    } catch (error) {
      console.warn("Failed to record HTML preview click:", error);
    }
  };

  doc.addEventListener("click", handleClick, true);
  return () => doc.removeEventListener("click", handleClick, true);
}
