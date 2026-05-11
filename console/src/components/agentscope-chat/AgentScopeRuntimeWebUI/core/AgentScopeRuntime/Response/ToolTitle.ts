const TOOL_DISPLAY_NAMES: Record<string, string> = {
  read_file: "读取文件",
  write_file: "写入文件",
  edit_file: "编辑文件",
  append_file: "追加文件",
  execute_shell_command: "执行操作",
  grep_search: "内容搜索",
  glob_search: "文件查找",
  memory_search: "记忆检索",
  browser_use: "网页操作",
  desktop_screenshot: "截取屏幕",
  get_current_time: "获取时间",
  set_user_timezone: "设置时区",
  view_image: "查看图片",
  view_video: "查看视频",
  send_file_to_user: "发送文件",
};

const TOOL_ACTION_NAMES: Record<string, string> = {
  read_file: "读取文件",
  write_file: "写入文件",
  edit_file: "编辑文件",
  append_file: "追加文件",
  grep_search: "搜索内容",
  glob_search: "查找文件",
  memory_search: "检索记忆",
  browser_use: "网页操作",
  view_image: "查看图片",
  view_video: "查看视频",
  send_file_to_user: "发送文件",
};

export function getToolDisplayName(toolName?: string, serverLabel?: string) {
  const label = toolName
    ? TOOL_DISPLAY_NAMES[toolName] || toolName
    : "工具操作";
  return serverLabel ? `[${serverLabel}] ${label}` : label;
}

function parseToolArguments(value: unknown): Record<string, any> | null {
  if (!value) return null;
  if (typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, any>;
  }
  if (typeof value !== "string") return null;

  const trimmed = value.trim();
  if (!trimmed.startsWith("{") || !trimmed.endsWith("}")) return null;
  try {
    const parsed = JSON.parse(trimmed);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed)
      ? parsed
      : null;
  } catch {
    return null;
  }
}

function compactText(value: unknown, maxLength = 64): string {
  if (typeof value !== "string") return "";
  const compacted = value.replace(/\s+/g, " ").trim();
  if (!compacted) return "";
  return compacted.length > maxLength
    ? `${compacted.slice(0, maxLength)}...`
    : compacted;
}

function basename(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) return "";
  try {
    const url = new URL(trimmed);
    const pathName = url.pathname.split("/").filter(Boolean).pop();
    return decodeURIComponent(pathName || url.hostname || trimmed);
  } catch {
    const segments = trimmed.split(/[\\/]/).filter(Boolean);
    return segments.pop() || trimmed;
  }
}

function compactUrl(value: string): string {
  try {
    const url = new URL(value.trim());
    const query =
      url.searchParams.get("q") ||
      url.searchParams.get("query") ||
      url.searchParams.get("keyword");
    if (query) return query;

    const pathName = url.pathname.replace(/^\/+|\/+$/g, "");
    return pathName ? `${url.hostname}/${pathName}` : url.hostname;
  } catch {
    return basename(value);
  }
}

function getArgumentHint(toolName: string, input: unknown): string {
  const args = parseToolArguments(input);
  if (!args || toolName === "execute_shell_command") return "";

  if (toolName === "browser_use") {
    if (typeof args.url === "string" && args.url.trim()) {
      return compactText(compactUrl(args.url));
    }
    return compactText(
      args.text || args.prompt_text || args.selector || args.action,
    );
  }

  const fileValue =
    args.file_path || args.path || args.filename || args.file_name || args.name;
  if (
    typeof fileValue === "string" &&
    [
      "read_file",
      "write_file",
      "edit_file",
      "append_file",
      "view_image",
      "view_video",
      "send_file_to_user",
    ].includes(toolName)
  ) {
    return compactText(basename(fileValue));
  }

  const commonValue =
    args.query || args.pattern || args.keyword || args.url || args.text;
  return compactText(commonValue);
}

function isUnsafeSummary(summary?: string): boolean {
  if (!summary || summary === "undefined") return true;
  return /[{[\]}]|"[^"]+"\s*:/.test(summary);
}

function isIncompleteSummary(summary: string): boolean {
  const actionWords =
    /读取|写入|编辑|追加|搜索|查找|检索|网页|浏览|打开|访问|点击|输入|调用|获取|查看|发送|执行|操作|查询|设置|截取/;
  return summary.trim().startsWith("正在") && !actionWords.test(summary);
}

export function buildToolTitle({
  loading,
  toolName,
  defaultTitle,
  input,
  summary,
}: {
  loading: boolean;
  toolName: string;
  defaultTitle: string;
  input: unknown;
  summary?: string;
}): string {
  const hint = getArgumentHint(toolName, input);
  if (!isUnsafeSummary(summary) && !isIncompleteSummary(summary as string)) {
    return summary as string;
  }

  const action = TOOL_ACTION_NAMES[toolName] || defaultTitle;
  if (hint) {
    return `${loading ? "正在" : ""}${action}：${hint}`;
  }
  return loading ? `正在调用：${defaultTitle}` : `调用工具：${defaultTitle}`;
}
