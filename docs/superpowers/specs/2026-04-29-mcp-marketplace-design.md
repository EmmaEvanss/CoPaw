# MCP 应用市场设计文档

> 创建时间：2026-04-29
> 状态：待审核

---

## 一、需求概述

本期在 `D:\workspace\copaw1\CoPaw` 中补完两类与 MCP 市场相关的能力：

1. 完成独立“我的 MCP”页面，用于管理当前用户本地 MCP。
2. 完成独立“应用市场”页面中的 `MCP` 子 Tab，用于浏览、上传、分发和删除市场 MCP。

页面组织方式继续参考 `D:\workspace\CmbCoworkAgent-main`：

- “我的 MCP”参考其 `MCP 连接器`
- “应用市场 -> MCP”参考其 `MarketPanel -> MCPs`
- 市场 MCP 详情参考其 `MCPConnectorDetail`

本期不新建独立市场体系，直接复用本项目现有 skills market 的前端页面骨架与后端 marketplace 骨架。

### 核心需求

| 功能点 | 说明 |
|--------|------|
| 我的 MCP | 独立页面，管理当前用户本地 MCP，支持创建、编辑、删除、启停、测试连接 |
| 来源标识 | 我的 MCP 为单列表，不分组，但保留来源标识区分“我创建的”和“市场分发的” |
| 发布到市场 | 管理员可在“我的 MCP”中将本地 MCP 发布到市场 |
| 应用市场 MCP Tab | 在独立应用市场页面中完成 `MCP` 子 Tab |
| 上传连接器 | 应用市场 `MCP` 子 Tab 提供“上传连接器”入口，交互沿用参考项目 |
| 市场分发 | 市场详情页提供“分发”操作，分发范围与返回结构对齐本项目现有 skills market |
| 市场删除 | 市场条目只提供“删除”，直接删除市场本地文件，不影响已分发用户 |
| 覆盖规则 | 同一 `client_key` 在市场中只有一条记录；重复发布或上传时直接覆盖，复用同一个 `item_id` |
| 复用现有能力 | MCP 市场复用现有分类、`bbk_ids` 可见范围、调用统计、用户统计、日志表 |

---

## 二、页面与入口结构

### 2.1 页面结构

本期直接复用本项目现有页面入口：

- `console/src/pages/Market/`：补完 `MCP` 子 Tab
- `console/src/pages/MyMCP/`：补完正式页面

其中：

- “我的 MCP”负责本地 MCP 管理与发布
- “应用市场 -> MCP”负责市场 MCP 的浏览、详情、上传、分发、删除

### 2.2 入口命名

保留两类入口，名称与语义分离：

- “我的 MCP”页使用 `发布到市场`
- “应用市场 -> MCP”使用 `上传连接器`

说明：

- “发布到市场”强调从当前用户本地 MCP 写入市场
- “上传连接器”强调在市场页直接新增或覆盖市场记录

---

## 三、架构总览

### 3.1 新增或扩展代码位置

| 层级 | 目录 | 说明 |
|------|------|------|
| 本地 MCP 路由 | `src/swe/app/routers/my_mcp.py` | 新建“我的 MCP”相关路由 |
| 市场浏览路由 | `market/src/market/app/routers/mcp_browse.py` | 新建市场 MCP 浏览与我的 MCP 列表路由 |
| 市场管理路由 | `market/src/market/app/routers/mcp_market.py` | 新建市场 MCP 上传、分发、删除路由 |
| 市场服务 | `market/src/market/marketplace/service.py` | 复用现有服务文件并扩展 MCP 相关方法 |
| 市场 Schema | `market/src/market/marketplace/schemas.py` | 复用现有 schema 文件并新增 MCP 相关模型 |
| 市场 FS | `market/src/market/marketplace/fs.py` | 复用现有 FS 文件并新增 MCP 路径与复制逻辑 |
| 市场模型 | `market/src/market/marketplace/models.py` | 复用现有模型文件并扩展 MCP 条目结构 |
| 我的 MCP 页面 | `console/src/pages/MyMCP/` | 用正式页面替换当前占位页 |
| 应用市场页面 | `console/src/pages/Market/` | 在现有 `Market` 页面中补完 MCP 分支 |
| 数据模型 | `src/swe/config/config.py` | 为 `MCPClientConfig` 扩展字段 |

### 3.2 与现有代码关系

```text
新增/扩展代码                         现有代码（复用）

/api/my-mcp ----------------------> load_agent_config()
                                     save_agent_config()
                                     MCPClientConfig（扩展字段）

/api/market/mcp ------------------> market.marketplace.service
                                     market.marketplace.schemas
                                     market.marketplace.fs
                                     swe_marketplace_operation_logs

/pages/MyMCP ---------------------> 现有 /pages/MyMCP 占位页

/pages/Market:MCP Tab ------------> 现有 /pages/Market 技能市场骨架
```

### 3.3 复用原则

- 不新建独立 marketplace 子系统
- 复用现有 market 的分类、可见范围、统计、日志和目录管理方式
- MCP 业务语义不继承 skills 的版本历史与下架逻辑
- 本地 MCP 仍复用现有 `agent.json -> mcp.clients` 存储

---

## 四、数据模型

### 4.1 本地 MCP 身份模型

本地 MCP 的稳定身份为 `client_key`。

`client_key` 规则：

- 在本地唯一
- 不支持重命名
- `name` 为显示名，可编辑但不影响身份

### 4.2 MCPClientConfig 扩展字段

在现有 `MCPClientConfig`（`src/swe/config/config.py:875-945`）基础上新增以下字段：

**扩展方式：** 一次性扩展，新增字段使用默认值，兼容现有 `agent.json` 配置文件。

```python
class MCPClientConfig(BaseModel):
    # 现有字段
    name: str
    description: str = ""
    enabled: bool = True
    transport: Literal["stdio", "streamable_http", "sse"] = "stdio"
    url: str = ""
    headers: Dict[str, str] = {}
    command: str = ""
    args: List[str] = []
    env: Dict[str, str] = {}
    cwd: str = ""

    # 新增字段
    source: str = ""                  # 空=我创建的；marketplace:{item_id}=市场分发的
    market_client_key: str = ""       # 市场来源的 client_key
    distributed_by: str = ""          # 分发者 user_id
    lazy_load: bool = False           # 懒加载预留字段
    created_at: str = ""              # ISO8601
    updated_at: str = ""              # ISO8601
```

说明：

- 本期不保留 `received_version`
- 本期不保留市场更新状态字段
- 市场删除后，本地仍保留 `source="marketplace:{item_id}"` 作为历史来源标记

### 4.3 本地来源规则

```python
def is_created_by_me(client: MCPClientConfig) -> bool:
    return client.source == ""


def is_distributed_from_market(client: MCPClientConfig) -> bool:
    return client.source.startswith("marketplace:")
```

### 4.4 市场身份模型

市场端采用“单条业务记录 + 持久条目标识”模型：

- `client_key` 是 MCP 的业务唯一键
- `item_id` 是市场条目的持久标识
- 市场中同一 `client_key` 永远只有一条当前记录
- 再次发布或上传时复用原 `item_id`
- 不保留版本历史
- 不保留下架状态

### 4.5 市场条目结构

市场索引继续复用现有 `index.json` 模式，但 MCP 条目扩展自己的字段。

目录结构：

```text
~/.swe.marketplace/
└── <source_id>/
    ├── index.json
    └── mcp/
        └── <item_id>/
            └── mcp.json
```

`index.json` 中的 MCP 条目：

```json
{
  "item_id": "uuid",
  "item_type": "mcp",
  "client_key": "weather-tool",
  "name": "Weather Tool",
  "description": "天气查询连接器",
  "creator_id": "user_id",
  "creator_name": "用户名",
  "category_id": 1,
  "bbk_ids": ["100"],
  "created_at": "ISO8601",
  "updated_at": "ISO8601"
}
```

`mcp.json`：

```json
{
  "client_key": "weather-tool",
  "config": {
    "name": "Weather Tool",
    "description": "天气查询连接器",
    "transport": "stdio",
    "command": "npx",
    "args": ["-y", "@example/mcp-server"],
    "env": {
      "API_KEY": "sk-proj-xxx"
    },
    "headers": {
      "Authorization": "Bearer xxx"
    },
    "cwd": "",
    "lazy_load": false
  }
}
```

### 4.6 敏感信息处理

本期沿用现有 `_mask_env_value` 脱敏逻辑：

- 市场条目完整保存 `env` 与 `headers` 原值（`mcp.json`）
- 市场详情页调用 `_mask_env_value` 脱敏展示（与现有"我的 MCP"展示逻辑一致）
- 分发时写入原值到目标用户本地配置
- 市场测试连接使用存储的原值进行连接测试
- 前端更新请求传入脱敏值时，后端 `_restore_original_values` 尝试恢复原值

---

## 五、API 设计

### 5.1 我的 MCP API

路由文件：`src/swe/app/routers/my_mcp.py`

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/my-mcp` | GET | 获取 MCP 单列表 |
| `/api/my-mcp/{client_key}` | GET | 获取单个 MCP 详情 |
| `/api/my-mcp` | POST | 创建本地 MCP |
| `/api/my-mcp/{client_key}` | PUT | 编辑本地 MCP |
| `/api/my-mcp/{client_key}` | DELETE | 删除本地 MCP |
| `/api/my-mcp/{client_key}/toggle` | PATCH | 启用/禁用 MCP |
| `/api/my-mcp/{client_key}/test` | POST | 测试本地 MCP 连接 |
| `/api/my-mcp/{client_key}/lazy-load` | PATCH | 更新 `lazy_load` 预留字段 |
| `/api/my-mcp/publish` | POST | 将本地 MCP 发布到市场 |

### 5.1.1 列表返回结构

```typescript
interface MyMCPListItem {
  client_key: string;
  name: string;
  description: string;
  transport: "stdio" | "streamable_http" | "sse";
  enabled: boolean;
  source: string;
  market_client_key?: string;
  created_at: string;
  updated_at: string;
}
```

### 5.1.2 发布请求与返回结构

```typescript
interface PublishMCPRequest {
  client_keys: string[];
  category_id?: number;
  bbk_ids?: string[];
}

interface PublishMCPResponse {
  results: Array<{
    client_key: string;
    item_id?: string;
    success: boolean;
    error?: string;
  }>;
}
```

说明：

- 前端允许多选
- 后端逐个处理并逐项返回结果
- 同一 `client_key` 在市场中已存在时，直接覆盖该市场记录并复用已有 `item_id`

### 5.2 市场 MCP API

路由文件：

- `market/src/market/app/routers/mcp_browse.py`
- `market/src/market/app/routers/mcp_market.py`

**路由定义方式（沿用现有 skills market 模式）：**

- 路由文件中定义路径：`/market/mcp`（不带 `/api` 前缀，与 `@router.get("/market/skills")` 一致）
- 应用级前缀：`/api`（`_app.py:88` → `app.include_router(api_router, prefix="/api")`）
- 完整对外暴露路径：`/api/market/mcp`

**代理机制：**

- vite 配置：`/api/market` → `http://127.0.0.1:8090`（`console/vite.config.ts:40-43`）
- 前端请求 `/api/market/mcp` → vite 代理 → market 服务收到 `/api/market/mcp`

| 接口（完整路径） | 方法 | 说明 |
|------|------|------|
| `/api/market/mcp` | GET | 获取市场 MCP 列表 |
| `/api/market/mcp/{item_id}` | GET | 获取市场 MCP 详情 |
| `/api/market/mcp/upload` | POST | 上传连接器到市场 |
| `/api/market/mcp/{item_id}/distribute` | POST | 分发给目标范围 |
| `/api/market/mcp/{item_id}/test` | POST | 测试市场详情中的连接器 |
| `/api/market/mcp/{item_id}` | DELETE | 删除市场 MCP，本地文件直接删除 |

### 5.2.1 市场列表返回结构

```typescript
interface MarketMCPItem {
  item_id: string;
  client_key: string;
  name: string;
  description: string;
  creator_id: string;
  creator_name: string;
  category_id: number | null;
  bbk_ids: string[];
  created_at: string | null;
  updated_at: string | null;
  call_count: number;
  user_count: number;
}
```

### 5.2.2 市场详情返回结构

```typescript
interface MarketMCPDetail extends MarketMCPItem {
  config: {
    transport: "stdio" | "streamable_http" | "sse";
    url: string;
    headers: Record<string, string>;
    command: string;
    args: string[];
    env: Record<string, string>;
    cwd: string;
    lazy_load: boolean;
  };
  user_stats: Array<{
    user_id: string;
    user_name: string;
    call_count: number;
  }>;
}
```

### 5.2.3 上传请求与返回结构

上传交互沿用 `CmbCoworkAgent-main` 的市场 MCP 上传设计。

请求格式：

`multipart/form-data`

字段说明：

- `file`：必须上传 `.json` 文件
- `name`：优先从文件解析；若解析出则前端锁定；解析失败时允许用文件名兜底
- `client_key`：优先从文件解析；解析失败时允许用文件名规范化兜底
- `description`：允许手填或修改
- `category_id`：复用现有 market 分类能力
- `bbk_ids`：复用现有可见范围能力

返回结构：

```typescript
interface UploadMarketMCPResponse {
  success: boolean;
  error?: string;
}
```

说明：

- 上传成功后前端关闭弹窗、提示成功并刷新列表
- 若市场中已存在相同 `client_key`，直接覆盖该市场记录并复用 `item_id`
- 只有文件内容不是合法 MCP 配置时才返回失败

### 5.2.4 分发请求与返回结构

分发范围与返回结构直接对齐现有 skills market：

```typescript
interface DistributeRequest {
  target_type: "all" | "bbk_id" | "user_id";
  target_values: string[];
}

interface DistributeResponse {
  distributed_count: number;
  item_id: string;
}
```

说明：

- 分发目标解析逻辑复用现有 market service
- 返回轻量结果，不做逐目标明细返回

### 5.2.5 删除返回结构

删除接口固定使用 `204 No Content`，前端按“成功提示 + 刷新列表”处理。

---

## 六、行为规则

### 6.1 我的 MCP

“我的 MCP”不再分 `全部 / 我创建的 / 我接收的`。

页面为单列表：

- 只搜索 `name`
- 按最近更新时间降序
- 通过来源标识区分：
  - 我创建的
  - 市场分发的

### 6.2 我创建的本地 MCP

可执行：

- 创建
- 编辑连接配置
- 启停
- 删除
- 测试连接
- 发布到市场

### 6.3 市场分发的本地 MCP

可执行：

- 启停
- 删除
- 测试连接

不可执行：

- 不可编辑连接配置
- 不可单独更新

### 6.4 市场记录覆盖规则

市场中同一 `client_key` 只有一条记录。

以下两种入口都遵守同一条规则：

- “我的 MCP -> 发布到市场”
- “应用市场 -> 上传连接器”

行为：

- 若市场中不存在该 `client_key`，则创建市场记录并生成 `item_id`
- 若市场中已存在该 `client_key`，则复用原 `item_id` 并直接全量覆盖市场记录
- 并发覆盖时，最后一次写入生效

时间字段规则：

- `created_at` 保留首次创建时间
- `updated_at` 在每次覆盖时刷新

### 6.5 分发覆盖规则

当目标用户本地已存在相同 `client_key` 时：

- 再次分发时直接覆盖该本地项
- 不区分该本地项原来是用户自建还是市场分发的
- 不生成重命名副本
- 本地 `enabled` 保持现有本地分发逻辑一致处理

### 6.6 市场删除规则

MCP 市场条目只有“删除”，没有“下架”。

删除行为：

- 直接删除市场索引中的 MCP 记录
- 直接删除对应 `mcp/<item_id>/mcp.json` 文件目录
- 不保留中间状态
- 不影响已经分发出去的用户本地副本

删除后的接收侧行为：

- 本地副本继续可启停、测试连接、删除
- 继续保留 `source="marketplace:{item_id}"`
- 来源字段仅表示历史来源，不再表示仍存在市场关联
- 不再支持跳转市场详情
- 不再与市场同步

### 6.7 接收侧更新规则

本期取消接收侧“更新”能力：

- 不提供“更新”按钮
- 不再检测市场更新
- 不存在“有更新”标记
- 后续覆盖只来自管理员再次分发

---

## 七、测试连接

### 7.1 本地测试连接

入口：

- 我的 MCP 详情页

行为：

- 测试当前用户本地 `agent.json` 中的实际配置

实现方式：

- 复用现有 `StatefulStdioClient` / `HttpStatefulClient` 类（`src/swe/app/mcp/stateful_client.py`）
- 创建客户端实例并调用 `connect()`
- 调用 `list_tools()` 获取工具列表

### 7.2 市场测试连接

入口：

- 应用市场 `MCP` 详情页

行为：

- 测试当前市场详情展示的连接器记录（使用存储的原值）
- 详情整体展示内容参考 `CmbCoworkAgent-main`
- 原有”安装”操作替换为”分发”

实现方式：

- 复用现有 `StatefulStdioClient` / `HttpStatefulClient` 类
- 使用市场 `mcp.json` 中存储的原值进行连接测试

### 7.3 返回结果

- 成功：返回工具列表
- 失败：返回错误信息
- 超时：30 秒，返回 `连接超时`
- 执行前先检查市场条目是否仍存在；若已删除，返回可读错误并由前端友好提示

---

## 八、懒加载

`lazy_load` 本期仅为预留字段与接口：

- 后端模型支持保存
- API 支持读写
- 前端默认隐藏懒加载开关
- 不承诺本期改变现有 MCP 实际注册与加载方式

---

## 九、权限控制

本期权限控制与本项目现有 market 体系保持一致：

- 前端使用 `manager` 控制管理员入口显隐
- market 服务端继续沿用现有 `X-Manager` 校验模式

权限矩阵：

| 操作 | 普通用户 | 管理员 |
|------|---------|--------|
| 创建本地 MCP | ✓ | ✓ |
| 编辑我创建的 MCP | ✓ | ✓ |
| 删除本地 MCP | ✓ | ✓ |
| 启用/禁用 | ✓ | ✓ |
| 测试本地连接 | ✓ | ✓ |
| 发布到市场 | - | ✓ |
| 市场上传连接器 | - | ✓ |
| 市场分发 | - | ✓ |
| 市场删除 | - | ✓ |

---

## 十、前端设计

### 10.1 我的 MCP

基于现有 `console/src/pages/MyMCP/index.tsx` 占位页补全为正式页面。

结构：

- 左侧列表 + 右侧详情的 Master-Detail 布局
- 左侧支持搜索
- 左侧不再做“全部 / 我创建的 / 我接收的”Tab
- 左侧列表项保留来源标识
- 右侧详情参考 `MCPConnectorDetail`

### 10.2 应用市场 -> MCP

基于现有 `console/src/pages/Market/MarketSkills.tsx` 中的 MCP 占位分支补完。

结构：

- 保留现有 `Market` 页面技能 / MCP 切换结构
- MCP 分支复用现有 market 页头、搜索、刷新、分类侧栏和详情抽屉组织方式
- 列表只搜索 `name`
- 详情页整体参考 `CmbCoworkAgent-main`，但将“安装”操作替换为“分发”

### 10.3 上传与发布入口

- 我的 MCP 页：`发布到市场`
- 应用市场 -> MCP：`上传连接器`

---

## 十一、核心流程

### 11.1 创建本地 MCP

```text
用户点击 [+]
  -> 打开创建弹窗
  -> 填写表单
  -> POST /api/my-mcp
  -> save_agent_config()
  -> 写入本地 agent.json
  -> source=""
```

### 11.2 发布到市场

```text
管理员在“我的 MCP”中选择一个或多个 client_key
  -> 点击“发布到市场”
  -> POST /api/my-mcp/publish
  -> 后端逐个处理
  -> 对每个 client_key：
       已存在同 client_key 的市场记录：复用 item_id 并覆盖
       不存在：创建新市场记录并生成 item_id
  -> 写入 marketplace index.json 与 mcp/<item_id>/mcp.json
  -> 记录 swe_marketplace_operation_logs
```

### 11.3 上传连接器到市场

```text
管理员在”应用市场 -> MCP”点击”上传连接器”
  -> 按参考项目交互上传 .json 文件
  -> POST /api/market/mcp/upload
  -> 解析 client_key / name
  -> 已存在同 client_key：复用 item_id 并覆盖
  -> 不存在：创建新记录并生成 item_id
  -> 写入市场文件
  -> 记录操作日志
  -> 返回 success/error
```

### 11.4 市场分发

```text
管理员在”应用市场 -> MCP”选择某个 item_id
  -> 在详情页点击”分发”
  -> 后端先检查市场条目是否仍存在
  -> 若已删除，则返回可读错误，前端友好提示
  -> 选择目标范围
  -> POST /api/market/mcp/{item_id}/distribute
  -> 解析目标用户集合（all / bbk_id / user_id）
  -> 逐个写入目标用户本地 agent.json 的 mcp.clients
  -> 若目标本地已存在同 client_key，则直接覆盖
  -> 写入来源字段：
       source=”marketplace:{item_id}”
       market_client_key=”{client_key}”
       distributed_by=”{admin_user_id}”
  -> 记录日志
  -> 返回 distributed_count + item_id
```

### 11.5 市场删除

```text
管理员在”应用市场 -> MCP”详情页点击”删除”
  -> DELETE /api/market/mcp/{item_id}
  -> 后端先检查市场条目是否仍存在
  -> 若已删除，则返回可读错误，前端友好提示
  -> 删除市场索引记录
  -> 删除对应市场文件目录
  -> 刷新市场列表
  -> 不回收已分发用户本地副本
```

---

## 十二、日志与统计

### 12.1 日志表

继续复用现有 `swe_marketplace_operation_logs`：

- upload
- publish
- distribute
- delete

MCP 场景下：

- `item_type = "mcp"`
- `item_id = MCP 市场条目的 item_id`
- `item_name = MCP 的 name`

### 12.2 分类与可见范围

MCP 市场复用现有 skills market 的：

- 分类表
- `category_id`
- `bbk_ids`
- 按 `source_id + bbk_id` 的可见性过滤

### 12.3 调用统计与用户统计

MCP 市场详情页复用现有统计能力思路：

- 列表展示 `call_count`、`user_count`
- 详情展示 `user_stats`
- 统计口径：新增 MCP 专用统计方法，按 tracing 表中 `mcp_server = client_key` 字段聚合（event_type 不限制或按 tool_invocation 过滤）
- 本期不按单个 MCP 工具维度拆分统计

**新增 MCP 专用统计 SQL（示例）：**

```sql
-- MCP 调用统计
SELECT
    COUNT(*) AS call_count,
    COUNT(DISTINCT user_id) AS user_count
FROM swe_tracing_spans
WHERE mcp_server = %s
  AND source_id = %s;

-- MCP 用户统计明细
SELECT
    user_id,
    MAX(COALESCE(metadata->>'$.user_name', '')) AS user_name,
    COUNT(*) AS call_count
FROM swe_tracing_spans
WHERE mcp_server = %s
  AND source_id = %s
GROUP BY user_id
ORDER BY call_count DESC
LIMIT 100;
```

---

## 十三、实施范围

| 模块 | 本期实施 | 说明 |
|------|---------|------|
| 我的 MCP 页面 | ✓ | 替换现有占位页 |
| 我的 MCP 创建/编辑/删除/启停 | ✓ | 单列表，不分组 |
| 我的 MCP 测试连接 | ✓ | |
| 发布到市场 | ✓ | 多选入口，逐个处理 |
| 应用市场页面中的 MCP 子 Tab | ✓ | 直接补完现有占位分支 |
| 市场上传连接器 | ✓ | 文件上传，轻量返回 |
| 市场详情 | ✓ | 详情 / 删除 / 分发 |
| 市场测试连接 | ✓ | |
| 市场分发 | ✓ | 请求/返回与现有 skills market 一致 |
| 市场删除 | ✓ | 直接删除市场文件 |
| 分类、可见范围、统计 | ✓ | 复用现有 market 能力 |
| lazy_load 字段与接口预留 | ✓ | 不保证真实生效 |
| 接收项更新 | - | 本期不做 |
| 下架能力 | - | 本期不做 |
| 历史版本 | - | 本期不做 |
| 逐目标分发明细返回 | - | 本期不做 |
