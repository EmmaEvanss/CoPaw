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

function normalizeText(value: string | null | undefined, maxLength: number) {
  const normalized = value?.replace(/\s+/g, " ").trim() || "";
  return normalized ? normalized.slice(0, maxLength) : null;
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
