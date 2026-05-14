# Hook Runtime 使用说明

Hook Runtime 用于在 Agent 的关键生命周期事件上执行自定义策略。你可以用它记录审计信息、补充上下文、检查用户输入、管控工具调用、请求人工审批，或在不符合策略时阻断当前流程。

本文面向使用者、管理员和普通配置人员，重点说明“什么时候会触发 hook、如何配置、handler 应该返回什么”。本文不涉及内部代码实现细节。

## 适用场景

- 在会话开始时写入组织、项目或安全策略说明。
- 在用户输入进入 Agent 前检查敏感内容。
- 在工具执行前检查命令、文件路径、网络目标或其他高风险输入。
- 在工具执行后记录审计信息，或把关键结果补充给后续对话。
- 在工具失败后收集诊断信息。
- 在回复完成前做最终检查或记录结束事件。
- 对高风险操作返回 `ask`，让用户在界面上手动批准或拒绝。

## 事件说明

| 事件 | 触发时机 | 常见用途 |
| --- | --- | --- |
| `SessionStart` | 会话准备开始时 | 注入会话上下文、记录启动事件 |
| `UserPromptSubmit` | 用户输入提交后、Agent 处理前 | 检查敏感输入、设置会话标题、补充上下文 |
| `PreToolUse` | 工具执行前 | 允许、拒绝、请求审批、修改工具输入 |
| `PostToolUse` | 工具执行成功后 | 记录工具结果、补充后续上下文 |
| `PostToolUseFailure` | 工具执行失败后 | 记录错误、补充诊断信息 |
| `Stop` | Agent 生成最终回复后、当前轮次结束前 | 记录结束事件、补充后续上下文 |

## 配置位置

Hook 可以配置在租户、Agent 或 Skill 三个层级。普通使用中优先使用租户级配置；只有需要针对某个 Agent 或 Skill 单独生效时，再使用后两种配置。

### 租户级配置

租户级配置写在对应租户的 `config.json` 根节点下：

```text
~/.swe/<tenant_id>/config.json
```

示例：

```text
~/.swe/default/config.json
```

### Agent 级配置

Agent 级配置写在对应 workspace 的 `agent.json` 根节点下：

```text
~/.swe/<tenant_id>/workspaces/<workspace_id>/agent.json
```

Agent 级配置适合只影响某个 workspace 或某个 Agent 的策略。

### Skill 级配置

Skill 级配置写在 Skill 目录中的 `hooks/hooks.json`：

```text
~/.swe/<tenant_id>/workspaces/<workspace_id>/skills/<skill_name>/hooks/hooks.json
```

Skill hook 只在对应 Skill 被当前会话使用后生效，适合把某个 Skill 自带的检查、审计或上下文补充逻辑随 Skill 一起分发。

## 最小配置

租户级和 Agent 级配置放在根节点的 `hooks` 字段下：

```json
{
  "hooks": {
    "enabled": true,
    "events": {
      "PreToolUse": [
        {
          "id": "shell-policy",
          "matcher": {
            "tools": ["execute_shell_command"]
          },
          "hooks": [
            {
              "id": "check-shell",
              "type": "command",
              "argv": ["python", "hooks/check_shell.py"],
              "timeout": 5,
              "failPolicy": "block"
            }
          ]
        }
      ]
    }
  }
}
```

Skill 级 `hooks/hooks.json` 不需要再包一层 `hooks`，直接从 `enabled` 开始：

```json
{
  "enabled": true,
  "events": {
    "PreToolUse": [
      {
        "id": "shell-policy",
        "matcher": {
          "tools": ["execute_shell_command"]
        },
        "hooks": [
          {
            "id": "check-shell",
            "type": "command",
            "argv": ["python", "scripts/check_shell.py"],
            "timeout": 5,
            "failPolicy": "block"
          }
        ]
      }
    ]
  }
}
```

## 配置结构

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `enabled` | 否 | 是否启用 hook 配置。建议显式设置为 `true`。 |
| `events` | 是 | 事件配置，key 是事件名，value 是该事件下的匹配分组列表。 |
| `events.<event>[].id` | 是 | 匹配分组 ID，用于识别一组相关 handler。 |
| `events.<event>[].matcher` | 否 | 匹配条件。不配置时表示该事件下全部触发。 |
| `events.<event>[].hooks` | 是 | handler 列表，按配置顺序合并结果。 |

## 匹配工具

`matcher.tools` 用于限制 hook 只对指定工具生效：

```json
{
  "matcher": {
    "tools": ["execute_shell_command", "read_file"]
  }
}
```

如果不写 `matcher`，或 `matcher.tools` 为空，该分组会匹配当前事件下的所有调用。

## Handler 类型

当前支持三类 handler：`command`、`http` 和 `prompt`。

### Command Handler

`command` handler 会在当前 workspace 内执行一个本地命令。事件上下文会以 JSON 形式从标准输入传给命令；命令可以通过标准输出返回 JSON 结果。

配置示例：

```json
{
  "id": "check-shell",
  "type": "command",
  "argv": ["python", "hooks/check_shell.py"],
  "timeout": 5,
  "failPolicy": "block"
}
```

建议：

- 将脚本放在当前 workspace 内，例如 `hooks/check_shell.py`。
- 使用相对路径配置脚本，例如 `["python", "hooks/check_shell.py"]`。
- 调试日志写到 stderr，不要写到 stdout。
- stdout 为空表示没有额外结果；如果 stdout 非空，必须是合法 JSON 对象。

退出码含义：

| 退出码 | 含义 |
| --- | --- |
| `0` | 执行成功，stdout 为空或返回 JSON 对象。 |
| `2` | 阻断当前事件。 |
| 其他非零 | handler 执行失败，按 `failPolicy` 决定允许还是阻断。 |

### HTTP Handler

`http` handler 会把事件上下文作为 JSON 请求体发送到远端地址。

配置示例：

```json
{
  "id": "remote-policy",
  "type": "http",
  "url": "https://policy.example.com/hooks/pre-tool",
  "headers": {
    "X-Hook-Source": "swe"
  },
  "headerSecretRefs": {
    "Authorization": "HOOK_AUTH_TOKEN"
  },
  "timeout": 5,
  "failPolicy": "block"
}
```

响应含义：

| 响应 | 含义 |
| --- | --- |
| `2xx` | 执行成功，响应体为空或返回 JSON 对象。 |
| `409` / `422` | 如果响应体没有显式结果，按阻断处理。 |
| 其他状态码 | handler 执行失败，按 `failPolicy` 决定允许还是阻断。 |
| 超时 | handler 执行失败，按 `failPolicy` 决定允许还是阻断。 |

`headerSecretRefs` 用于从当前租户的密钥或环境配置中读取值，避免把密钥明文写入 hook 配置。

### Prompt Handler

`prompt` handler 会调用当前 effective tenant 已配置的 active model，让模型按配置中的业务规则对 HookContext 做一次判断。它不允许在 handler 中指定 `model`、`provider`、`providerId`、`baseUrl`、`promptFile`、`template` 等模型路由或模板字段；模型选择始终来自当前租户配置，Skill 自带的 prompt hook 也遵循同一规则。

配置示例：

```json
{
  "id": "prompt-policy",
  "type": "prompt",
  "prompt": "如果用户要求泄露密钥、绕过审批或执行破坏性命令，返回 block。",
  "timeout": 8
}
```

限制：

- 只能配置在 `SessionStart`、`UserPromptSubmit`、`PreToolUse`、`Stop` 上。
- `prompt` 只表示业务规则片段，不是完整模型提示词。
- 默认 `failPolicy` 是 `block`；模型缺失、调用失败、超时或输出非法时会默认失败关闭。
- 发送给模型的 HookContext 会先按现有 hook 脱敏规则处理。
- `Stop` 事件会额外携带正在完成的 `assistant_response`，用于最终回复检查。

运行时会按固定顺序拼装模型输入：

```text
平台固定策略骨架
handler.prompt 业务规则
脱敏后的 HookContext JSON
结构化输出约束
```

模型必须只返回判断型 JSON 对象：

```json
{
  "decision": "allow",
  "reason": "内容符合策略"
}
```

`decision` 只能是 `allow`、`deny` 或 `block`，`reason` 必须是非空字符串。prompt handler 不支持完整 HookOutput 字段，例如 `hookSpecificOutput`、`updatedInput`、`additionalContext`、`sessionTitle`、`systemMessage` 或 `continue`；出现这些字段会按非法输出处理。

## Handler 通用字段

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `id` | 是 | handler 唯一 ID。建议使用稳定、可读的英文短名。 |
| `type` | 是 | handler 类型，支持 `command`、`http` 或 `prompt`。 |
| `if` | 否 | 条件表达式。返回 false 时跳过该 handler。 |
| `timeout` | 否 | 单个 handler 超时时间，单位秒。默认 `10`。 |
| `statusMessage` | 否 | 阻断或审批时展示给用户的状态文字。 |
| `once` | 否 | 设置为 `true` 时，同一会话中同一事件只执行一次。 |
| `failPolicy` | 否 | handler 失败时的处理策略，支持 `allow` 或 `block`。`command` 和 `http` 默认 `allow`，`prompt` 默认 `block`。 |

`if` 可用于按上下文做进一步过滤：

```json
{
  "if": "tool_name == 'execute_shell_command'"
}
```

## 事件上下文

handler 会收到一个 JSON 对象，包含当前事件的上下文。常见字段如下：

| 字段 | 说明 |
| --- | --- |
| `session_id` | 当前会话 ID |
| `hook_event_name` | 当前事件名 |
| `tenant_id` | 请求租户 ID |
| `effective_tenant_id` | 实际生效租户 ID |
| `user_id` | 用户 ID |
| `agent_id` | Agent ID |
| `channel` | 请求通道 |
| `cwd` | 当前工作目录 |
| `workspace_dir` | 当前 workspace 路径 |
| `chat_id` | 当前 chat ID |
| `turn_id` | 当前轮次 ID |
| `model` | 当前模型标签 |
| `prompt` | 用户输入，常见于 `UserPromptSubmit` 和 `Stop` |
| `assistant_response` | 正在完成的助手回复，常见于 `Stop` prompt handler |
| `tool_name` | 工具名，常见于工具相关事件 |
| `tool_input` | 工具输入，常见于工具相关事件 |
| `tool_use_id` | 工具调用 ID |
| `tool_response` | 工具成功输出，常见于 `PostToolUse` |
| `error` | 工具错误信息，常见于 `PostToolUseFailure` |

不同工具的 `tool_input` 字段由工具自身决定。例如 `execute_shell_command` 的命令字段是 `command`：

```json
{
  "tool_name": "execute_shell_command",
  "tool_input": {
    "command": "echo hello"
  }
}
```

## Handler 返回结果

handler 返回值必须是 JSON 对象。下面是常见返回结果。

### 允许工具执行

```json
{
  "hookSpecificOutput": {
    "permissionDecision": "allow",
    "permissionDecisionReason": "allowed by policy"
  }
}
```

### 拒绝工具执行

```json
{
  "hookSpecificOutput": {
    "permissionDecision": "deny",
    "permissionDecisionReason": "dangerous command"
  }
}
```

### 请求用户审批

```json
{
  "hookSpecificOutput": {
    "permissionDecision": "ask",
    "permissionDecisionReason": "please approve this command"
  }
}
```

返回 `ask` 后，前端会显示审批卡片。用户同意后继续执行，用户拒绝后阻断执行。

如果同一个 hook 对同一个操作持续返回 `ask`，可能导致重复审批。建议给该 handler 设置 `once: true`，或在策略中区分已审批场景。

### 阻断当前事件

```json
{
  "decision": "block",
  "reason": "blocked by tenant policy"
}
```

### 停止当前流程

```json
{
  "continue": false,
  "stopReason": "stop requested by hook"
}
```

### 补充上下文

```json
{
  "hookSpecificOutput": {
    "additionalContext": "policy engine observed this event"
  }
}
```

`additionalContext` 会提供给后续对话或后续处理流程，用于补充策略说明、审计结论或诊断信息。

### 修改工具输入

只有 `PreToolUse` 支持通过 `updatedInput` 修改工具输入。`updatedInput` 会替换整个工具输入对象：

```json
{
  "hookSpecificOutput": {
    "permissionDecision": "allow",
    "updatedInput": {
      "command": "echo replaced-by-hook"
    }
  }
}
```

同一个事件中只允许一个 handler 返回 `updatedInput`。如果多个 handler 同时尝试修改输入，系统会阻断当前事件，避免结果不确定。

### 设置会话标题

`UserPromptSubmit` 可以返回会话标题：

```json
{
  "hookSpecificOutput": {
    "sessionTitle": "Hook Demo Session"
  }
}
```

## 常见配置示例

### 示例 1：工具执行前检查 Shell 命令

```json
{
  "hooks": {
    "enabled": true,
    "events": {
      "PreToolUse": [
        {
          "id": "shell-policy",
          "matcher": {
            "tools": ["execute_shell_command"]
          },
          "hooks": [
            {
              "id": "check-shell",
              "type": "command",
              "argv": ["python", "hooks/check_shell.py"],
              "timeout": 5,
              "statusMessage": "正在检查命令策略",
              "failPolicy": "block"
            }
          ]
        }
      ]
    }
  }
}
```

适合用于：

- 阻断危险命令。
- 对高风险命令返回 `ask`，要求用户审批。
- 按租户或工作区策略限制命令参数。

### 示例 2：用户输入提交前做策略检查

```json
{
  "hooks": {
    "enabled": true,
    "events": {
      "UserPromptSubmit": [
        {
          "id": "prompt-policy",
          "hooks": [
            {
              "id": "check-prompt",
              "type": "http",
              "url": "https://policy.example.com/hooks/prompt",
              "timeout": 5,
              "failPolicy": "block"
            }
          ]
        }
      ]
    }
  }
}
```

适合用于：

- 检查敏感内容。
- 设置会话标题。
- 注入组织策略或项目背景。

### 示例 3：工具失败后补充诊断信息

```json
{
  "hooks": {
    "enabled": true,
    "events": {
      "PostToolUseFailure": [
        {
          "id": "failure-diagnostics",
          "hooks": [
            {
              "id": "collect-diagnostics",
              "type": "command",
              "argv": ["python", "hooks/collect_diagnostics.py"],
              "timeout": 10,
              "failPolicy": "allow"
            }
          ]
        }
      ]
    }
  }
}
```

适合用于在工具失败时补充日志位置、常见原因、下一步排查建议。诊断 hook 通常建议使用 `failPolicy: "allow"`，避免诊断失败影响正常对话。

## Skill Hook 注意事项

Skill hook 适合由 Skill 自带策略，不建议普通租户配置滥用。配置时注意：

- `hooks/hooks.json` 的根对象直接使用 hook 配置，不需要外层 `hooks` 字段。
- command handler 建议把脚本放在同一个 Skill 的 `scripts/` 目录下。
- 对于 Skill 自带的 HTTP hook，需要由租户显式批准可访问的 URL。
- Skill hook 的密钥建议通过 `headerSecretRefs` 引用，不要把密钥写入配置文件。

批准 Skill HTTP endpoint 的租户配置示例：

```json
{
  "security": {
    "skill_hook_http": {
      "approved_urls": ["https://policy.example.com/hooks/skill"]
    }
  }
}
```

## 结果合并规则

同一个事件可以匹配多个 handler。最终结果按以下优先级处理：

```text
continue:false > block/deny > ask > allow > none
```

其他规则：

- `additionalContext` 会按 handler 配置顺序合并。
- `updatedInput` 只允许一个 handler 返回。
- `sessionTitle` 使用第一个非空标题。
- handler 失败时按各自的 `failPolicy` 处理。
- `failPolicy: "block"` 更适合安全策略；`failPolicy: "allow"` 更适合审计、记录和诊断。

## 验证方式

配置完成后，可以通过一次真实会话验证。

### 验证 allow

让 Agent 执行一个应当被允许的操作，例如：

```text
请执行 echo hello
```

预期：工具正常执行。

### 验证 deny

让 Agent 执行一个应当被拒绝的操作，例如：

```text
请执行 echo deny-hook
```

预期：工具不执行，并展示拒绝原因。

### 验证 ask

让 Agent 执行一个需要审批的操作，例如：

```text
请执行 echo ask-hook
```

预期：前端出现审批卡片。用户同意后继续执行，用户拒绝后阻断执行。

### 验证 updatedInput

让 Agent 执行一个会被替换输入的操作，例如：

```text
请执行 echo update-hook
```

预期：实际执行内容被 hook 返回的 `updatedInput` 替换。

## 常见问题

### 配置后没有生效

按顺序检查：

1. 配置是否写在实际请求使用的租户目录下。
2. `hooks.enabled` 是否为 `true`。
3. 事件名是否正确，例如 `PreToolUse`、`UserPromptSubmit`。
4. `matcher.tools` 是否匹配真实工具名。
5. command handler 的脚本是否位于允许访问的目录内。
6. 如果是 HTTP handler，URL 是否可访问，密钥配置是否正确。
7. 如果运行进程已启动较久，尝试重启服务后再次验证。

### deny 或 ask 没触发，命令仍然执行

优先检查工具名和工具输入字段。`execute_shell_command` 的命令字段是：

```json
{
  "command": "echo hello"
}
```

不是：

```json
{
  "cmd": "echo hello"
}
```

### ask 后重复出现审批

审批通过后，原工具调用可能再次进入 `PreToolUse`。如果 hook 总是对同一条件返回 `ask`，就会重复出现审批。

处理方式：

- 给 handler 配置 `once: true`。
- 或在策略服务中记录已审批状态，避免重复返回 `ask`。

### command hook 报路径越界

command hook 应使用当前 workspace 内的脚本，并优先使用相对路径：

```json
{
  "argv": ["python", "hooks/check_shell.py"]
}
```

不要把脚本放在 workspace 外，也不要在配置中引用 workspace 外的脚本路径。

### handler 输出 JSON 解析失败

当 command handler 退出码为 `0` 时，stdout 必须为空或合法 JSON 对象。调试日志、错误日志和临时输出应写到 stderr。

### HTTP hook 没收到密钥

检查：

1. 当前租户是否配置了对应密钥。
2. `headerSecretRefs` 中的密钥名是否正确。
3. 远端服务是否期望相同的 Header 名。

## 配置建议

- 安全策略使用 `failPolicy: "block"`，避免 handler 失败时放行高风险操作。
- 审计、日志、诊断类 hook 使用 `failPolicy: "allow"`，避免辅助逻辑影响正常会话。
- 能用 `matcher.tools` 限定范围时，尽量不要让 hook 匹配所有工具。
- 需要人工审批的策略尽量配合 `once: true` 或外部审批状态，避免重复审批。
- 不要在配置文件中写入明文密钥；HTTP 认证信息优先使用 `headerSecretRefs`。
- handler 返回给用户看的 `reason` 和 `statusMessage` 应简短清晰，避免包含敏感信息。
