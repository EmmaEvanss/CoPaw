/**
 * 生成 MCP 的稳定 client_key。
 *
 * 规则：
 * - 可读部分优先保留英文、数字和中文拼音
 * - 唯一性通过原始名称的稳定短哈希保证
 * - 不再使用时间戳兜底，避免中文名每次生成不同 key
 */
import * as pinyin from "tiny-pinyin";

const DEFAULT_SLUG = "mcp";
const MAX_SLUG_LENGTH = 48;
const HANZI_RE = /[\u4e00-\u9fff]/;

function normalizeSlug(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "-")
    .replace(/[^a-z0-9_-]/g, "-")
    .replace(/-+/g, "-")
    .replace(/^[-_]+|[-_]+$/g, "");
}

function truncateSlug(value: string): string {
  return value.slice(0, MAX_SLUG_LENGTH).replace(/^[-_]+|[-_]+$/g, "");
}

/**
 * 使用 FNV-1a 生成稳定短哈希。
 *
 * 这里只需要短且稳定的后缀，不追求密码学安全。
 */
function shortHash(input: string): string {
  let hash = 0x811c9dc5;
  for (let idx = 0; idx < input.length; idx += 1) {
    hash ^= input.charCodeAt(idx);
    hash = Math.imul(hash, 0x01000193);
  }
  return (hash >>> 0).toString(16).padStart(8, "0").slice(0, 4);
}

function buildReadableSlug(name: string): string {
  const trimmed = name.trim();
  if (!trimmed) return "";

  const source =
    HANZI_RE.test(trimmed) && pinyin.isSupported()
      ? pinyin.convertToPinyin(trimmed, "-", true)
      : trimmed.toLowerCase();

  const normalized = normalizeSlug(source);
  return truncateSlug(normalized);
}

export function buildClientKey(name: string): string {
  const trimmed = name.trim();
  const slug = buildReadableSlug(trimmed) || DEFAULT_SLUG;
  return `${slug}-${shortHash(trimmed)}`;
}
