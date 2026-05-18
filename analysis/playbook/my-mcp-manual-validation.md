# MyMCP 本地手工验证指南

这份文档用于本地环境快速验证 `MyMCP` 在不同用户、不同来源、不同应用和管理员身份下的行为，不依赖额外后端改造，也不需要修改非 MCP 代码。

## 适用范围

- 页面：`console/src/pages/MyMCP`
- 后端：`market/src/market/app/routers/my_mcp.py`
- 本地验证方式：
  - 浏览器地址栏参数
  - 浏览器 `sessionStorage`

## 核心隔离维度

`MyMCP` 当前实际依赖以下请求头做隔离：

- `X-User-Id`：用户身份标识
- `X-Tenant-Id`：租户隔离标识（**iframe 场景下与 X-User-Id 同值**）
- `X-Source-Id`：来源标识（与 `tenant_id` 一起决定运行时 `scope_id`）
- `X-Agent-Id`：应用隔离标识
- `X-Manager`：管理员权限标识

**iframe 嵌入场景下的身份转换链路**：

```text
父窗口 postMessage USER_DATA：
├── sapId → iframeStore.userId → X-User-Id + X-Tenant-Id（同一值）
├── source → iframeStore.source → X-Source-Id
├── manager → iframeStore.manager → 上架按钮判断 + X-Manager header
└── isSuperManager → iframeStore.isSuperManager → 上架按钮判断
```

**关键转换规则**：

- `sapId`（用户 SAP ID）直接作为 `X-Tenant-Id` 使用，**无 source → tenant 转换**
- iframe 场景下：**用户身份 = 租户身份**
- `source_id` 会与 `tenant_id` 一起编码成独立运行时 `scope_id`
- `default_{source}` 只保留为模板目录命名，不再是实际 runtime tenant 目录

对应代码入口：

- 前端 header 构造：
  [console/src/api/authHeaders.ts](../../console/src/api/authHeaders.ts)
- 前端 iframe 上下文：
  [console/src/utils/iframeMessage.ts](../../console/src/utils/iframeMessage.ts)
- 前端身份解析：
  [console/src/utils/identity.ts](../../console/src/utils/identity.ts)
- 后端请求上下文解析：
  [market/src/market/app/my_mcp_helpers.py](../../market/src/market/app/my_mcp_helpers.py)

## 推荐验证方式

优先使用浏览器开发者工具控制台修改 `sessionStorage`。

原因：

- 改动范围最小
- 不需要改源码
- 可以快速切换用户、来源、应用和管理员身份

## 控制台初始化脚本

打开 `MyMCP` 页面后：

1. 按 `F12`
2. 切到 `Console`
3. 粘贴以下脚本并回车执行

```js
function readStore(key, fallback = { state: {} }) {
  const raw = sessionStorage.getItem(key);
  return raw ? JSON.parse(raw) : fallback;
}

function writeStore(key, value) {
  sessionStorage.setItem(key, JSON.stringify(value));
}

function reloadPage() {
  location.reload();
}

function switchUser(userId) {
  const store = readStore("swe-iframe-context");
  store.state = {
    ...store.state,
    userId,
  };
  writeStore("swe-iframe-context", store);
  reloadPage();
}

function switchSource(source) {
  const store = readStore("swe-iframe-context");
  store.state = {
    ...store.state,
    source,
  };
  writeStore("swe-iframe-context", store);
  reloadPage();
}

function switchIframeContext({
  userId,
  clawName,
  source,
  manager,
  isSuperManager,
}) {
  const store = readStore("swe-iframe-context");
  store.state = {
    ...store.state,
    ...(userId !== undefined ? { userId } : {}),
    ...(clawName !== undefined ? { clawName } : {}),
    ...(source !== undefined ? { source } : {}),
    ...(manager !== undefined ? { manager: !!manager } : {}),
    ...(isSuperManager !== undefined
      ? { isSuperManager: !!isSuperManager }
      : {}),
  };
  writeStore("swe-iframe-context", store);
  reloadPage();
}

function switchManager(enabled) {
  const store = readStore("swe-iframe-context");
  store.state = {
    ...store.state,
    manager: !!enabled,
    isSuperManager: false,
  };
  writeStore("swe-iframe-context", store);
  reloadPage();
}

function switchSuperManager(enabled) {
  const store = readStore("swe-iframe-context");
  store.state = {
    ...store.state,
    manager: false,
    isSuperManager: !!enabled,
  };
  writeStore("swe-iframe-context", store);
  reloadPage();
}

function switchAgent(agentId) {
  const store = readStore("swe-agent-storage");
  store.state = {
    ...store.state,
    selectedAgent: agentId,
  };
  writeStore("swe-agent-storage", store);
  reloadPage();
}

function switchUserName(clawName) {
  const store = readStore("swe-iframe-context");
  store.state = {
    ...store.state,
    clawName,
  };
  writeStore("swe-iframe-context", store);
  reloadPage();
}

function showMyMcpContext() {
  const iframe = readStore("swe-iframe-context");
  const agent = readStore("swe-agent-storage");
  console.log("userId =", iframe.state?.userId);
  console.log("clawName =", iframe.state?.clawName);
  console.log("source =", iframe.state?.source);
  console.log("manager =", iframe.state?.manager);
  console.log("isSuperManager =", iframe.state?.isSuperManager);
  console.log("selectedAgent =", agent.state?.selectedAgent);
}

function resetMyMcpContext() {
  sessionStorage.removeItem("swe-iframe-context");
  sessionStorage.removeItem("swe-agent-storage");
  reloadPage();
}
```

## 常用命令

```js
showMyMcpContext()
switchUser("user_a")
switchUserName("张三")
switchSource("SRC_A")
switchIframeContext({
  userId: "user_a",
  clawName: "张三",
  source: "SRC_A",
  manager: false,
  isSuperManager: false,
})
switchAgent("default")
switchManager(true)
switchSuperManager(true)
resetMyMcpContext()
```

## 地址栏参数说明

支持通过地址栏带：

```text
?origin=Y
```

这条链路会触发：

- `hideMenu: true`
- `source: "RMASSIST"`

但不会自动注入：

- `manager`
- `isSuperManager`

所以管理员验证仍建议通过 `sessionStorage` 处理。

## 用户名如何传入

`MyMCP` 上架到市场时，创建人名称来自 iframe 上下文中的：

- `clawName`

实际链路是：

```text
iframeStore.clawName
-> MyMCP 页面中的 userName
-> 上架请求头 X-User-Name
-> 市场 index.json 中的 creator_name
```

如果本地验证时没有传 `clawName`，前端会回退成：

```text
"Unknown"
```

因此，当你需要验证：

- 市场条目 `creator_name`
- 市场详情页“创建人”
- 不同用户上架后的创建人名称

请不要只传 `userId`，而要一起传 `clawName`。

推荐做法：

```js
switchIframeContext({
  userId: "user_a",
  clawName: "张三",
  source: "SRC_A",
  manager: true,
  isSuperManager: false,
})
```

如果只想单独改用户名：

```js
switchUserName("张三")
```

## 真实使用场景说明

本地手工验证时，建议尽量模拟真实 iframe 注入行为。

真实场景下切换来源时，前端上下文通常会一起带入：

- `userId`
- `clawName`
- `manager`
- `isSuperManager`
- `source`

因此，不建议只长期单独调用：

```js
switchSource("SRC_A")
```

更接近真实使用场景的方式是：

```js
switchIframeContext({
  userId: "user_a",
  clawName: "张三",
  source: "SRC_A",
  manager: false,
  isSuperManager: false,
})
```

后文所有“切换来源”的案例，都建议按这种完整上下文切换来执行。

## 手工验证步骤

### 1. 基线检查

1. 打开 `MyMCP` 页面
2. 执行：

```js
showMyMcpContext()
```

确认当前：

- `userId`
- `source`
- `selectedAgent`
- `manager`
- `isSuperManager`

### 2. 验证不同用户

执行：

```js
switchIframeContext({
  userId: "user_a",
  clawName: "张三",
  source: "",
  manager: false,
  isSuperManager: false,
})
```

检查：

- 列表是否正常加载
- 新建的 MCP 是否可见
- 编辑和保存是否正常

再执行：

```js
switchIframeContext({
  userId: "user_c",
  clawName: "李四",
  source: "dqb_source",
  manager: false,
  isSuperManager: false,
})
```

检查：

- `user_a` 下创建的 MCP 是否不可见
- 当前用户列表是否独立

预期：

- 不同用户之间 `MyMCP` 列表和详情互不影响

### 3. 验证不同应用

先固定一个用户，例如：

```js
switchIframeContext({
  userId: "user_a",
  clawName: "张三",
  source: "",
  manager: false,
  isSuperManager: false,
})
```

再切换应用：

```js
switchAgent("default")
```

记录当前列表后，再切另一个 agent：

```js
switchAgent("your_other_agent_id")
```

检查：

- 列表是否变化
- 新建 MCP 是否仅出现在当前 agent 下

预期：

- 不同应用之间 MCP 配置隔离

### 4. 验证不同来源

固定用户和应用后，依次执行：

```js
switchIframeContext({
  userId: "default",
  clawName: "默认用户",
  source: "",
  manager: false,
  isSuperManager: false,
})
switchIframeContext({
  userId: "default",
  clawName: "默认用户",
  source: "SRC_A",
  manager: false,
  isSuperManager: false,
})
switchIframeContext({
  userId: "default",
  clawName: "默认用户",
  source: "SRC_B",
  manager: false,
  isSuperManager: false,
})
```

每次刷新后检查：

- 列表是否变化
- 当前来源下新增的 MCP 是否只存在于该来源

预期：

- 不同 `source` 下的配置互相隔离

### 5. 验证管理员能力

先切成普通用户：

```js
switchIframeContext({
  userId: "user_a",
  clawName: "张三",
  source: "SRC_A",
  manager: false,
  isSuperManager: false,
})
```

检查：

- “上架”按钮是否不可用或不可见

再切管理员：

```js
switchIframeContext({
  userId: "user_a",
  clawName: "张三",
  source: "SRC_A",
  manager: true,
  isSuperManager: false,
})
```

检查：

- “上架”按钮是否出现
- 上架弹窗是否可打开
- 提交后是否成功

再切超级管理员：

```js
switchIframeContext({
  userId: "user_a",
  clawName: "张三",
  source: "SRC_A",
  manager: false,
  isSuperManager: true,
})
```

检查：

- 管理员相关能力是否与普通管理员一致

### 6. 验证市场分发来源条目

找到 `source` 以 `marketplace:` 开头的条目，检查：

- 是否允许启停
- 是否允许测试连接
- 是否允许删除
- 是否禁止编辑连接配置
- 是否不显示“上架”

预期：

- 市场分发条目保留运行态能力
- 不允许当成本地自建 MCP 修改配置

### 7. 验证新增和编辑即时生效

在任一上下文下执行：

1. 新建一个 MCP
2. 打开编辑弹窗
3. 新增请求头
4. 保存
5. 立即再次打开编辑弹窗

检查：

- 新增的请求头是否立刻可见
- 输入请求头时焦点是否稳定

预期：

- 不需要手动刷新页面或列表
- 新增请求头能立即回显

## 推荐验证矩阵

建议最少覆盖以下组合：

| 维度 | 场景 |
|------|------|
| 用户 | `user_a` / `user_b` |
| 来源 | `""` / `SRC_A` / `SRC_B` |
| 应用 | `default` / 另一个 agent |
| 权限 | 普通用户 / 管理员 / 超级管理员 |

## 验证注意事项

### 1. 新用户首次继承 `default` 模板是正常行为

当你把 `userId` 切到一个全新的值，例如：

- `user_a`
- `user_b`

前端会自动发送：

- `X-User-Id = user_a`
- `X-Tenant-Id = user_a`（**与 X-User-Id 同值**）

后端会把它当成新的 tenant 做初始化。初始化时会从 `default` 模板复制一套基础配置过去，这里面包括：

- `config.json`
- `workspaces/default/agent.json`

因此你第一次切到新用户时，如果看到 `default` 下已有的 MCP 被带入到：

- `~/.swe/user_a/`
- `~/.swe/user_b/`

这是正常的模板继承行为，不代表多个用户共享同一个文件。

验证重点应放在：

- 继承完成后，`user_a` 的修改是否不会影响 `user_b`
- `user_a` 的修改是否不会回写到 `default`

### 2. 非 `default` 用户下，`source` 也会继续拆分 runtime scope

当前来源隔离规则是：

- `tenant_id = default` 且有 `source_id`
  - 生效目录：`scope.v1.<default>.<source>`
- `tenant_id != default`
  - 生效目录：`scope.v1.<tenant_id>.<source_id>`
  - `source_id` 不再被忽略

这意味着：

- 在 `default` 用户下切换 `source`，能看到明显的来源隔离
- 在 `user_a` / `user_b` 这种非 `default` 用户下切换 `source`，也会进入不同的 runtime scope

如果出现下面这种现象，应视为缺陷而不是预期行为：

```text
同一个 user_a
切换 source = SRC_A / SRC_B
仍然落在同一个 runtime 目录
列表数据也完全相同
```

当前正确行为应为：

- `user_a + SRC_A` 与 `user_a + SRC_B` 使用不同的 runtime scope
- `user_a + SRC_A` 与 `user_b + SRC_A` 也继续保持不同的 runtime scope

## 验证完成后的恢复

执行：

```js
resetMyMcpContext()
```

用于清理本地 `sessionStorage`，恢复默认行为。

## 补充验证案例

### 案例 1：相同来源，不同用户

目的：

- 验证”同一个来源”下，不同用户是否各自独立

**隔离原理**：

- iframe 场景下，`userId` 直接作为 `tenant_id` 使用
- 不同 userId = 不同 tenant_id = 不同目录
- source_id 会继续参与 runtime scope 计算，即使 tenant_id 不是 `default`

步骤：

1. 固定来源：

```js
switchIframeContext({
  userId: "user_a",
  clawName: "张三",
  source: "SRC_A",
  manager: false,
  isSuperManager: false,
})
```

实际产生的 headers：
- `X-User-Id = "user_a"`
- `X-Tenant-Id = "user_a"`（与 X-User-Id 同值）
- `X-User-Name = "张三"`
- `X-Source-Id = "SRC_A"`（参与 runtime scope 计算）

后端生效目录：`~/.swe/scope.v1.<user_a>.<SRC_A>/`

2. 新建一个 MCP，例如 `user-a-only`
3. 再切到用户 B，但保持相同来源：

```js
switchIframeContext({
  userId: "user_b",
  clawName: "李四",
  source: "SRC_A",
  manager: false,
  isSuperManager: false,
})
```

实际产生的 headers：
- `X-User-Id = "user_b"`
- `X-Tenant-Id = "user_b"`
- `X-User-Name = "李四"`
- `X-Source-Id = "SRC_A"`（参与 runtime scope 计算）

后端生效目录：`~/.swe/scope.v1.<user_b>.<SRC_A>/`

4. 检查 `user-a-only` 是否不可见
5. 在 `user_b` 下新建一个不同的 MCP
6. 切回 `user_a` 且保持相同来源，再确认 `user_b` 的 MCP 不可见

预期：

- 同一来源下，不同用户互相不可见
- 两个用户各自继承模板后独立演化
- **隔离同时来自 tenant_id 与 source_id 共同组成的 runtime scope**

### 案例 2：相同用户，不同来源（所有用户都应隔离）

目的：

- 验证 `default` 用户下来源隔离是否生效

**隔离原理**：

- 任意 tenant 只要携带 `source_id`，都会进入独立 runtime scope
- 生效目录是编码后的 `scope_id`，例如 `scope.v1.<tenant>.<SRC_A>`
- `default_{source}` 仅是模板目录，不是实际运行时目录

步骤：

1. 切回默认用户：

```js
switchIframeContext({
  userId: "default",
  clawName: "默认用户",
  source: "SRC_A",
  manager: false,
  isSuperManager: false,
})
```

实际产生的 headers：
- `X-User-Id = "default"`
- `X-Tenant-Id = "default"`
- `X-User-Name = "默认用户"`
- `X-Source-Id = "SRC_A"`

后端生效目录：`~/.swe/scope.v1.<default>.<SRC_A>/`

2. 新建一个 MCP，例如 `src-a-only`
3. 切来源 B：

```js
switchIframeContext({
  userId: "default",
  clawName: "默认用户",
  source: "SRC_B",
  manager: false,
  isSuperManager: false,
})
```

后端生效目录：`~/.swe/scope.v1.<default>.<SRC_B>/`

4. 检查 `src-a-only` 是否不可见
5. 在 `SRC_B` 下再新建一个 MCP
6. 切回 `SRC_A`，确认只看到自己来源下的数据

预期：

- `tenant + source` 组合之间互相隔离
- 不同 source 产生不同 runtime scope 目录

**补充验证**：若将 userId 切换为非 default 值（如 `user_a`），切换 source 仍应产生隔离效果，列表数据不应保持一致。

### 案例 3：相同用户，相同来源，不同应用

目的：

- 验证 Agent 级别隔离是否生效

**隔离原理**：

- Agent 隔离通过 `X-Agent-Id` header 实现
- 与 tenant/source 隔离独立运作
- source 会先切分 runtime scope，Agent 隔离再在该 scope 内继续生效

步骤：

1. 固定用户和来源：

```js
switchIframeContext({
  userId: "user_a",
  clawName: "张三",
  source: "SRC_A",
  manager: false,
  isSuperManager: false,
})
```

实际产生的 headers：
- `X-User-Id = "user_a"`
- `X-Tenant-Id = "user_a"`
- `X-User-Name = "张三"`
- `X-Source-Id = "SRC_A"`（参与 runtime scope 计算）
- 后端生效目录：`~/.swe/scope.v1.<user_a>.<SRC_A>/`

2. 切应用 A：

```js
switchAgent("default")
```

3. 新建一个 MCP，例如 `agent-a-only`
4. 切应用 B：

```js
switchAgent("your_other_agent_id")
```

5. 检查 `agent-a-only` 是否不可见
6. 在应用 B 下新建另一个 MCP
7. 切回应用 A，确认应用 B 的 MCP 不可见

预期：

- 同一个用户、同一个来源下，不同应用互相隔离
- Agent 隔离在 MCP 配置文件内部实现（`agent.json` 中 `mcpServers` 字段）

### 案例 4：相同用户，相同应用，普通用户与管理员

目的：

- 验证权限只影响管理功能，不影响数据归属

**隔离原理**：

- `manager` 和 `isSuperManager` 来自 iframe 父窗口的 postMessage
- 仅影响上架按钮显示和 `X-Manager` header 发送
- 不影响 tenant_id 或数据归属

步骤：

1. 固定用户、来源、应用
2. 切普通用户：

```js
switchIframeContext({
  userId: "user_a",
  clawName: "张三",
  source: "SRC_A",
  manager: false,
  isSuperManager: false,
})
```

实际产生的 headers：
- `X-User-Id = "user_a"`
- `X-Tenant-Id = "user_a"`
- `X-User-Name = "张三"`
- 无 `X-Manager` header（上架按钮隐藏）

3. 记录当前列表与详情
4. 切管理员：

```js
switchIframeContext({
  userId: "user_a",
  clawName: "张三",
  source: "SRC_A",
  manager: true,
  isSuperManager: false,
})
```

实际产生的 headers：
- `X-User-Id = "user_a"`
- `X-Tenant-Id = "user_a"`（**与普通用户状态相同**）
- `X-User-Name = "张三"`
- 管理员操作时发送 `X-Manager: "true"`

5. 检查：
   - “上架”是否出现
   - 列表数据本身是否没有变化（因为 tenant_id 未变）

预期：

- 权限变化只影响管理按钮
- 不应影响当前 `MyMCP` 数据集合
- **数据归属由 userId（即 tenant_id）决定，不由 manager 决定**

### 案例 5：市场分发项与本地自建项混合验证

目的：

- 验证来源不同的条目在同一列表中的能力边界

**source 字段来源**：

- 本地自建 MCP：source 为空或用户自定义值
- 市场分发 MCP：source 以 `marketplace:` 开头（如 `marketplace:xxx`）

步骤：

1. 准备一个本地自建 MCP（source 为空或自定义）
2. 准备一个 `source = marketplace:...` 的市场分发项
3. 分别点开详情，检查按钮差异

预期：

- 本地自建项：
  - 可编辑
  - 可上架（需 manager 权限）
  - 可启停
  - 可测试
  - 可删除
- 市场分发项：
  - 不可编辑连接配置
  - 不可上架
  - 可启停
  - 可测试
  - 可删除
