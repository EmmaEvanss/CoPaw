## Why

Swe 的 unified hook runtime 目前只能通过本地命令或远端 HTTP 服务执行策略判断。租户、Agent 和 Skill 需要一种更轻量的方式，让当前租户已配置的大模型基于 HookContext 做单轮策略判断，同时不引入新的模型配置面或事件改写能力。

## What Changes

- 新增 `prompt` hook handler 类型，用于调用当前 effective tenant 的 active model 对 HookContext 做单轮判断。
- `prompt` 字段只表示 hook 业务规则片段，运行时按固定顺序拼装最终模型输入：平台固定骨架、业务规则、HookContext JSON、结构化输出约束。
- MVP 只接受判断型结构化输出：JSON 对象只能包含 `decision` 和 `reason`，其中 `decision` 为 `allow`、`deny` 或 `block`，`reason` 为非空字符串。
- `prompt` handler 只允许配置在实际可阻断的事件上：`SessionStart`、`UserPromptSubmit`、`PreToolUse`、`Stop`。
- tenant、agent、skill 三类 hook 来源都可以声明 `prompt` handler；skill-owned prompt hook 仍使用当前 effective tenant 的 active model。
- `prompt` handler 与 `command`、`http` handler 共享现有 `if`、`timeout`、`statusMessage`、`once`、`failPolicy` 字段，并沿用现有并发执行与 deterministic merge 规则；但 prompt handler 默认 `failPolicy` 为 `block`，且配置中显式拒绝模型/Provider override 字段。
- prompt handler 执行时必须从当前 HookContext 显式绑定租户上下文，并对发送给模型的 HookContext JSON 应用已有敏感字段脱敏。
- 非法模型输出、超时、模型调用失败或 active model 缺失都视为 handler failure，并按 `failPolicy` 处理。

## Capabilities

### New Capabilities

- `prompt-hook-handler`: 定义 prompt hook handler 的配置、事件约束、模型调用、结构化输出和失败处理语义。

### Modified Capabilities

None.

## Impact

- Affected backend code:
  - `src/swe/agents/hook_runtime/models.py`
  - `src/swe/agents/hook_runtime/executor.py`
  - `src/swe/agents/hook_runtime/output.py`
  - `src/swe/agents/hook_runtime/skill_loader.py`
  - `src/swe/agents/model_factory.py` integration points used by hook execution
- Affected docs:
  - `docs/hook-runtime.md`
- Affected tests:
  - hook config model validation
  - prompt handler execution and output parsing
  - resolver/event validation
  - skill hook loading
  - fail-policy behavior for model errors and invalid outputs
- No frontend API or UI changes are required for the MVP.
