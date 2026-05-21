/**
 * 临时前端白名单配置。
 *
 * - 填写 SAP 号时，仅这些用户展示回答反馈卡片
 * - 填写 "*" 时，所有用户展示
 * - 置为空数组时，所有用户都不展示
 * - 支持通过 window.__env__.responseFeedbackUserWhitelist 运行时覆盖
 */
const DEFAULT_WHITELIST: readonly string[] = ["*"];

function getWhitelist(): readonly string[] {
  if (
    typeof window !== "undefined" &&
    window.__env__?.responseFeedbackUserWhitelist !== undefined
  ) {
    return window.__env__.responseFeedbackUserWhitelist;
  }
  return DEFAULT_WHITELIST;
}

export const RESPONSE_FEEDBACK_USER_WHITELIST: readonly string[] =
  getWhitelist();

export function isResponseFeedbackUserAllowed(userSap?: string | null) {
  if (RESPONSE_FEEDBACK_USER_WHITELIST.includes("*")) {
    return true;
  }
  if (!userSap) {
    return false;
  }
  return RESPONSE_FEEDBACK_USER_WHITELIST.includes(userSap);
}
