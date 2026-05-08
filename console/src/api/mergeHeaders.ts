/**
 * 统一合并请求头。
 *
 * 说明：
 * - 基础上下文头统一来自 authHeaders
 * - 调用方可通过 extra 覆盖或补充业务相关头
 */
import { buildAuthHeaders } from "./authHeaders";

export function mergeHeaders(extra?: Record<string, string>): RequestInit {
  const base = buildAuthHeaders();
  const merged: Record<string, string> = { ...base, ...(extra || {}) };
  return { headers: new Headers(merged) };
}
