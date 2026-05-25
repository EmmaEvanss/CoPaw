# MCP 失败兜底 Hook 设计

## 背景

需要构建一个 skill 级 hook，在 MCP 工具调用失败时，为后续对话注入统一兜底话术，让模型基于这段上下文自行回复用户。

当前范围只覆盖 MCP 工具调用失败场景，不处理成功结果字段缺失，不区分 `401`、`500` 等失败类型，也不直接在 hook 中输出最终回复。

## 目标

- 在 skill 内提供可分发的最小 hook 实现。
- 当目标 MCP 工具调用进入 `PostToolUseFailure` 事件时，向后续对话注入统一兜底话术。
- 保持实现独立，不修改现有 hook runtime。

## 非目标

- 不修改 `src/swe/agents/hook_runtime/` 运行时代码。
- 不解析结构化状态码；只依赖失败事件中的 `error` 字符串。
- 不在 hook 中直接阻断或替代模型回复。
- 不覆盖成功场景或字段校验场景。

## 现状约束

根据 `docs/hook/hook-runtime.md` 与当前代码实现：

- skill 级 hook 通过 `hooks/hooks.json` 配置。
- `PostToolUseFailure` 的 hook 上下文可拿到 `tool_name`、`tool_input`、`tool_use_id` 和 `error`。
- 当前失败事件没有单独的 `status_code` 字段，因此不能稳定区分 `401`、`500`，只能根据“工具已失败”这一事实处理。
- `additionalContext` 会被写入后续对话记忆，适合承载统一兜底提示。

## 方案选择

### 方案一：skill 级 `PostToolUseFailure + command handler`

在 skill 目录下提供一个本地脚本，读取 hook runtime 通过 stdin 传入的 `HookContext` JSON；当检测到失败事件且 `error` 非空时，返回包含统一兜底话术的 `additionalContext`。

优点：

- 无外部服务依赖，部署最轻。
- 与 skill 一起分发，边界清晰。
- 最符合当前需求。

缺点：

- 后续如果要做集中审计或远程策略，需要另行扩展。

### 方案二：skill 级 `PostToolUseFailure + http handler`

把失败上下文发送到本地或远端 HTTP 服务，再由服务返回 `additionalContext`。

优点：

- 后续可扩展到统一策略服务。

缺点：

- 引入额外进程或远端依赖，当前场景明显偏重。

### 方案三：租户级或 Agent 级失败 hook

把相同逻辑做成全局 hook，而不是 skill 自带 hook。

优点：

- 可一次配置全局生效。

缺点：

- 与当前“做成一个 skill”的目标不一致。
- 不利于把逻辑作为独立能力包复用或分发。

## 最终方案

采用方案一：新增一个最小 skill 级 `PostToolUseFailure` command hook。

## 目录设计

建议先以文档化样例方式放在 `docs/hook/` 下，便于验证和演示：

```text
docs/hook/mcp-failure-fallback-demo/
├── SKILL.md
├── hooks/
│   └── hooks.json
└── scripts/
    └── mcp_failure_fallback.py
```

后续如果需要正式启用，可按相同结构复制到实际 skill 目录。

## Hook 配置设计

`hooks/hooks.json` 使用 `PostToolUseFailure` 事件，并通过 `matcher.tools` 限制到目标 MCP 工具名。

配置语义如下：

- `enabled: true`
- `events.PostToolUseFailure`
- 单个 matcher group
- 单个 `command` handler
- `argv` 指向 `scripts/mcp_failure_fallback.py`
- `failPolicy: "allow"`

这里选择 `allow` 的原因是：该 hook 属于兜底文案补充，不应该因为脚本自身失败而影响原始错误传播。

## 脚本行为设计

### 输入

脚本从 stdin 读取 hook runtime 传入的 JSON 对象，重点字段为：

- `hook_event_name`
- `tool_name`
- `tool_input`
- `tool_use_id`
- `error`

### 输出

当满足以下条件时返回：

- 事件为 `PostToolUseFailure`
- `error` 为非空字符串

返回：

```json
{
  "hookSpecificOutput": {
    "additionalContext": [
      "MCP 工具调用失败。请不要继续依赖本次工具结果，改为向用户说明当前调用暂时失败，并使用统一兜底话术回复。"
    ]
  }
}
```

其余情况返回空对象：

```json
{}
```

### 设计说明

- 统一兜底话术先固定为单一文案，不按错误类型分支。
- `additionalContext` 使用列表形式，便于后续扩展更多诊断说明。
- 脚本只负责注入提示，不负责拼出最终用户可见回复。

## 运行时链路

预期链路如下：

1. Agent 调用目标 MCP 工具。
2. 工具执行抛错。
3. `ToolGuardMixin._acting()` 捕获异常并触发 `PostToolUseFailure` hook。
4. skill 级 command handler 脚本读取 `error`。
5. 脚本返回 `additionalContext`。
6. hook runtime 将 `additionalContext` 写入记忆。
7. 模型在后续对话中读取该上下文，自行输出统一兜底回复。

## 测试设计

采用最小测试集，先验证脚本逻辑，再验证配置结构。

### 脚本单测

覆盖以下场景：

- 失败事件且 `error` 非空时，返回 `additionalContext`
- `error` 为空时，返回空对象
- 非 `PostToolUseFailure` 事件时，返回空对象
- 非法 JSON 输入时，脚本返回失败退出码或明确错误

### 配置与集成检查

覆盖以下场景：

- `hooks/hooks.json` 能被 skill hook loader 正常加载
- `argv` 中脚本路径满足 skill runtime 的目录约束
- `matcher.tools` 生效范围符合预期

## 风险与边界

- 当前 hook 上下文缺少结构化状态码，因此无法可靠地区分 `401` 与 `500`。
- 该方案依赖模型遵循 `additionalContext` 中的提示；它不是硬编码回复器。
- 如果目标 MCP 工具的失败并未抛到 `PostToolUseFailure`，则该方案不会生效；这属于工具调用链外的限制，不在本次范围内处理。

## 实施步骤

1. 新建样例 skill 目录与文档。
2. 先为脚本编写失败注入相关测试。
3. 实现 `mcp_failure_fallback.py`。
4. 编写 `hooks/hooks.json` 与 `SKILL.md`。
5. 运行针对性 `pytest` 验证脚本和 hook 加载行为。

## 验收标准

- MCP 工具抛错后，hook 能向记忆写入统一兜底提示。
- hook 脚本自身失败不会阻断原始工具失败链路。
- 不修改现有 hook runtime 代码即可完成能力交付。
