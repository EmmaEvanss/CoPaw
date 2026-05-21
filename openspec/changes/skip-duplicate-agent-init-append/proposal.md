## Why

`/api/agent/init` 当前每次调用都会直接向目标 Markdown 文件末尾追加 `text`。当调用方因为刷新、重试或重复初始化再次提交相同内容时，文件末尾会被重复写入相同片段，导致初始化信息膨胀，并让后续读取结果出现重复噪音。

这个接口本质上承担“初始化补充”的职责，应该具备尾部幂等性：同一段初始化内容已经位于文件末尾时，不应再次写入。

## What Changes

- 调整 `/api/agent/init` 的追加逻辑，在写入前先判断当前目标文件末尾是否与请求 `text` 完全一致。
- 当文件末尾已与请求 `text` 一致时，接口跳过本次追加，保持文件内容不变。
- 当目标文件不存在，或文件末尾与请求 `text` 不一致时，接口继续按现有方式追加内容。
- 为该行为补充单元测试，覆盖“尾部一致时跳过”和“尾部不一致时追加”两类场景。

## Capabilities

### New Capabilities

- `agent-init-append`: `/api/agent/init` 在追加初始化内容前执行文件尾部去重判断，避免重复写入相同尾部内容。

### Modified Capabilities

- （无现有 spec 需要修改）

## Impact

- **接口行为**：`POST /api/agent/init` 从“无条件追加”调整为“尾部不同才追加”的幂等追加语义。
- **后端代码**：
  - `src/swe/app/routers/agent.py`
  - `src/swe/agents/memory/agent_md_manager.py`
- **测试**：
  - `tests/unit/routers/test_agent_init.py`
- **兼容性**：不新增外部依赖，不改变请求参数；调用成功时仍保持 200 响应。
