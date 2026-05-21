import type { FeedbackRecord } from "@/api/types/feedback";
import {
  resolveGroupTimestamp,
  resolveFeedbackResponseId,
  resolveFeedbackTraceId,
  type ChatRuntimeResponseCardData,
  type ChatTaskRunGroupCardData,
} from "./messageMeta";

export interface FeedbackLookupMap {
  byKey: Record<string, FeedbackRecord>;
  byLocalKey: Record<string, FeedbackRecord>;
  items: FeedbackRecord[];
}

function normalizeLookupId(value?: string | null): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return trimmed || null;
}

function feedbackLookupKey(
  kind: "response" | "trace",
  value?: string | null,
): string | null {
  const normalized = normalizeLookupId(value);
  return normalized ? `${kind}:${normalized}` : null;
}

export function buildFeedbackLookup(
  items: FeedbackRecord[],
  responses: ChatRuntimeResponseCardData[] = [],
): FeedbackLookupMap {
  const byKey = items.reduce<Record<string, FeedbackRecord>>((acc, item) => {
    const responseKey = feedbackLookupKey("response", item.response_id);
    const traceKey = feedbackLookupKey("trace", item.trace_id);
    if (responseKey) {
      acc[responseKey] = item;
    }
    if (traceKey) {
      acc[traceKey] = item;
    }
    return acc;
  }, {});
  const byLocalKey = buildTimeFallbackLookup(items, responses, byKey);
  return { byKey, byLocalKey, items };
}

function normalizeTextPart(value: unknown): string {
  if (typeof value === "string") return value;
  if (!value || typeof value !== "object") return "";
  const record = value as Record<string, unknown>;
  if (typeof record.text === "string") return record.text;
  if (typeof record.content === "string") return record.content;
  return "";
}

function normalizeResponseText(response: ChatRuntimeResponseCardData): string {
  const output = Array.isArray(response.output) ? response.output : [];
  return output
    .map((message) => {
      const content = (message as { content?: unknown }).content;
      if (Array.isArray(content)) {
        return content.map(normalizeTextPart).join("");
      }
      return normalizeTextPart(content);
    })
    .join("\n")
    .replace(/\s+/g, " ")
    .trim();
}

function readResponseOriginalId(
  response: ChatRuntimeResponseCardData,
): string | null {
  const output = Array.isArray(response.output) ? response.output : [];
  return output.reduce<string | null>((found, message) => {
    if (found) return found;
    if (message?.role !== "assistant") return null;
    const metadata = (message as { metadata?: unknown }).metadata;
    if (!metadata || typeof metadata !== "object") return null;
    const record = metadata as Record<string, unknown>;
    const direct = record.original_id || record.originalId;
    return typeof direct === "string" && direct.trim() ? direct : null;
  }, null);
}

export function resolveFeedbackLocalKeys(
  response: ChatRuntimeResponseCardData,
): string[] {
  const keys: string[] = [];
  const pushKey = (key: string | null) => {
    if (key && !keys.includes(key)) {
      keys.push(key);
    }
  };

  const responseId = resolveFeedbackResponseId(response);
  pushKey(responseId ? `response:${responseId}` : null);

  const traceId = resolveFeedbackTraceId(response);
  pushKey(traceId ? `trace:${traceId}` : null);

  const originalId = readResponseOriginalId(response);
  pushKey(originalId ? `original:${originalId}` : null);

  const text = normalizeResponseText(response);
  const timestamp = response.headerMeta?.timestamp || response.created_at;
  pushKey(
    text && timestamp ? `content:${timestamp}:${text.slice(0, 256)}` : null,
  );
  return keys;
}

export function resolveFeedbackLocalKey(
  response: ChatRuntimeResponseCardData,
): string | null {
  return resolveFeedbackLocalKeys(response)[0] || null;
}

function parseFeedbackTime(item: FeedbackRecord): number | null {
  const value = item.updated_at || item.created_at;
  if (!value) return null;
  const timestamp = Date.parse(value);
  return Number.isNaN(timestamp) ? null : timestamp;
}

function resolveResponseTimestamp(
  response: ChatRuntimeResponseCardData,
): number | null {
  if (response.headerMeta?.timestamp) return response.headerMeta.timestamp;
  const output = Array.isArray(response.output) ? response.output : [];
  return (
    resolveGroupTimestamp(
      output.map((message) => ({
        timestamp: (message as { timestamp?: unknown }).timestamp,
      })),
    ) ??
    response.created_at ??
    null
  );
}

function hasHistoricalOriginalId(response: ChatRuntimeResponseCardData): boolean {
  return Boolean(readResponseOriginalId(response));
}

function hasExactFeedbackMatch(
  response: ChatRuntimeResponseCardData,
  byKey: Record<string, FeedbackRecord>,
): boolean {
  const responseKey = feedbackLookupKey(
    "response",
    resolveFeedbackResponseId(response),
  );
  if (responseKey && byKey[responseKey]) return true;

  const traceKey = feedbackLookupKey("trace", resolveFeedbackTraceId(response));
  return Boolean(traceKey && byKey[traceKey]);
}

function buildTimeFallbackLookup(
  items: FeedbackRecord[],
  responses: ChatRuntimeResponseCardData[],
  byKey: Record<string, FeedbackRecord>,
): Record<string, FeedbackRecord> {
  const maxDiffMs = 10 * 60 * 1000;
  const exactMatchedFeedbackIds = new Set<number>();
  const candidates = responses
    .map((response, index) => ({
      response,
      index,
      timestamp: resolveResponseTimestamp(response),
      keys: resolveFeedbackLocalKeys(response),
    }))
    .filter(
      (candidate) =>
        candidate.timestamp &&
        candidate.keys.length > 0 &&
        !resolveFeedbackTraceId(candidate.response) &&
        hasHistoricalOriginalId(candidate.response) &&
        !hasExactFeedbackMatch(candidate.response, byKey),
    ) as Array<{
    response: ChatRuntimeResponseCardData;
    index: number;
    timestamp: number;
    keys: string[];
  }>;

  for (const response of responses) {
    const responseKey = feedbackLookupKey(
      "response",
      resolveFeedbackResponseId(response),
    );
    const traceKey = feedbackLookupKey("trace", resolveFeedbackTraceId(response));
    const matched = (responseKey && byKey[responseKey]) || (traceKey && byKey[traceKey]);
    if (matched?.id) {
      exactMatchedFeedbackIds.add(matched.id);
    }
  }

  const fallbackItems = items
    .filter((item) => !exactMatchedFeedbackIds.has(item.id))
    .map((item) => ({
      item,
      timestamp: parseFeedbackTime(item),
    }))
    .filter((entry): entry is { item: FeedbackRecord; timestamp: number } =>
      Boolean(entry.timestamp),
    )
    .sort((left, right) => left.timestamp - right.timestamp);

  const usedResponseIndexes = new Set<number>();
  const byLocalKey: Record<string, FeedbackRecord> = {};

  for (const entry of fallbackItems) {
    const matched = candidates
      .filter((candidate) => {
        if (usedResponseIndexes.has(candidate.index)) return false;
        const diff = entry.timestamp - candidate.timestamp;
        return diff >= 0 && diff <= maxDiffMs;
      })
      .sort((left, right) => {
        const leftDiff = entry.timestamp - left.timestamp;
        const rightDiff = entry.timestamp - right.timestamp;
        if (leftDiff !== rightDiff) return leftDiff - rightDiff;
        return left.index - right.index;
      })[0];

    if (!matched) continue;
    usedResponseIndexes.add(matched.index);
    for (const key of matched.keys) {
      byLocalKey[key] = entry.item;
    }
  }

  return byLocalKey;
}

export function collectFeedbackResponsesFromMessages(
  messages: Array<{ cards?: Array<{ code?: string; data?: unknown }> }> = [],
): ChatRuntimeResponseCardData[] {
  const responses: ChatRuntimeResponseCardData[] = [];
  for (const message of messages) {
    for (const card of message.cards || []) {
      if (card.code === "AgentScopeRuntimeResponseCard") {
        responses.push(card.data as ChatRuntimeResponseCardData);
      }
      if (card.code === "TaskRunGroupCard") {
        const data = card.data as ChatTaskRunGroupCardData;
        responses.push(
          ...collectFeedbackResponsesFromMessages(data.finalMessages || []),
        );
      }
    }
  }
  return responses;
}

export function findFeedbackForResponse(
  lookup: FeedbackLookupMap | undefined,
  response: ChatRuntimeResponseCardData,
): FeedbackRecord | null {
  if (!lookup) return null;

  const responseKey = feedbackLookupKey(
    "response",
    resolveFeedbackResponseId(response),
  );
  if (responseKey && lookup.byKey[responseKey]) {
    return lookup.byKey[responseKey];
  }

  const traceKey = feedbackLookupKey("trace", resolveFeedbackTraceId(response));
  if (traceKey && lookup.byKey[traceKey]) {
    return lookup.byKey[traceKey];
  }

  for (const localKey of resolveFeedbackLocalKeys(response)) {
    if (lookup.byLocalKey[localKey]) {
      return lookup.byLocalKey[localKey];
    }
  }

  return null;
}
