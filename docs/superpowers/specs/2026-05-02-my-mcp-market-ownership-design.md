# MyMCP 归属 Market 服务设计

> 创建时间：2026-05-02
> 状态：待审核

---

## 一、目标

将“我的 MCP”全部后端能力从 `swe` 主服务迁移到 `market` 服务。

迁移完成后：

- `MyMCP` 前端只调用 `market` 服务接口
- `market` 服务直接读写用户本地 `~/.swe` 下的 agent 配置
- `market` 服务直接负责 MCP 配置保存后的 agent reload
- `swe` 主服务不再保留 `src/swe/app/routers/my_mcp.py`

本次迁移不改变现有前端页面交互，不重做数据模型，不改变市场 MCP 的现有接口语义。

---

## 二、迁移动机

当前实现中，“我的 MCP”被拆在两套服务中：

- 本地 MCP 管理由 `swe` 的 `my_mcp.py` 提供
- 市场 MCP 的浏览、上传、分发、删除由 `market` 提供

这会带来三个问题：

1. 前端 `MyMCP` 页面同时依赖两套后端边界，职责不清晰。
2. MCP 相关功能已经被定位为市场体系的一部分，但本地管理仍停留在 `swe` 路由层。
3. 发布到市场、测试连接、来源处理、权限判断分散在两套服务中，不利于后续继续演进。

因此本次将 `MyMCP` 全量收拢到 `market` 服务。

---

## 三、范围

### 3.1 迁移到 `market` 的能力

以下能力全部迁移到 `market`：

- 我的 MCP 列表
- 我的 MCP 详情
- 创建 MCP
- 编辑 MCP
- 删除 MCP
- 启停 MCP
- 测试连接
- 草稿测试连接
- 上架到市场

### 3.2 不在本次迁移中改变的内容

- `MyMCP` 前端页面布局与交互
- 市场 MCP 的浏览、上传、分发、删除接口
- MCP 市场数据落盘格式
- `MCPClientConfig` 现有字段定义
- 已经接收的市场 MCP 的来源标记语义

---

## 四、目标结构

### 4.1 路由归属

迁移后路由归属如下：

| 能力 | 服务 | 路由前缀 |
|------|------|----------|
| 我的 MCP 列表/详情/创建/编辑/删除/启停/测试 | `market` | `/api/my-mcp` |
| 我的 MCP 上架到市场 | `market` | `/api/my-mcp/publish` |
| 市场 MCP 浏览 | `market` | `/api/market/mcp` |
| 市场 MCP 上传/分发/删除 | `market` | `/api/market/mcp/...` |

说明：

- `MyMCP` 的 URL 前缀保持 `/api/my-mcp`，避免前端页面不必要的路径重构。
- 但实现文件与运行服务迁移到 `market`。

### 4.2 文件归属

迁移后文件结构如下：

| 文件 | 处理方式 | 说明 |
|------|----------|------|
| `src/swe/app/routers/my_mcp.py` | 删除 | `swe` 不再保留该路由 |
| `market/src/market/app/routers/my_mcp.py` | 新建 | 复制并改造原 `my_mcp.py` |
| `market/src/market/app/routers/__init__.py` | 修改 | 注册 `my_mcp` 路由 |
| `console/src/api/modules/myMcp.ts` | 修改 | 请求目标切到 `market` 服务 |

---

## 五、实现原则

### 5.1 优先复制 `swe` 现有逻辑

本次不重新设计 `MyMCP` 后端逻辑，优先直接复制 `swe` 现有实现，再在 `market` 中替换不兼容依赖。

优先复用的内容包括：

- Pydantic 请求/响应模型
- MCP 详情脱敏逻辑
- `env` / `headers` 的掩码恢复逻辑
- 测试连接逻辑
- 市场分发 MCP 的敏感字段禁止编辑逻辑

### 5.2 只替换 `market` 无法直接运行的依赖

原 `my_mcp.py` 中不能直接在 `market` 中工作的依赖，必须替换为 `market` 可用实现：

- `get_agent_and_config_for_request()`
- `schedule_agent_reload()`
- 依赖 `request.app.state.multi_agent_manager` 的上下文路径

其它逻辑尽量保持原样。

---

## 六、核心依赖替换

### 6.1 配置读取与保存

`market` 服务直接复用 `swe.config.config` 中的配置模型和保存函数。

迁移后仍然使用：

- `MCPClientConfig`
- `MCPConfig`
- `load_agent_config()`
- `save_agent_config()`

`market` 新增一层本地 helper，用于从请求头中解析：

- `tenant_id`
- `source_id`
- `user_id`
- `agent_id`

并据此定位目标用户的 agent 配置文件。

### 6.2 请求上下文解析

原 `swe` 的 `get_agent_and_config_for_request()` 同时承担：

- 解析 tenant/source/user/agent
- 获取 workspace
- 获取 agent 配置

迁移到 `market` 后，这个 helper 不能直接复用，因为 `market` 没有 `multi_agent_manager` 和 workspace。

因此 `market` 中新增替代 helper，只负责：

1. 从 header 和 request state 解析用户上下文
2. 解析目标 agent，默认 `default`
3. 直接从本地文件加载 agent 配置

本期不在 `market` 中引入 workspace 概念。

### 6.3 Agent reload

这是本次迁移唯一高风险点。

迁移后，`market` 不再通过 `schedule_agent_reload()` 间接调用 `swe` 路由层逻辑，而是直接复用 `swe` 中可调用的 reload 入口。

要求：

- reload 行为与 `swe` 当前 `MyMCP` 保存后行为保持一致
- reload 必须是非阻塞触发
- 保存配置失败时不触发 reload
- reload 失败不回滚配置，但必须记录日志

如果 `market` 里无法直接复用原有 reload helper，则在 `market` 中新增一个薄封装 helper，对接 `swe` 已有的 reload 入口。

本次不重新设计独立 reload 协议。

---

## 七、接口设计

### 7.1 保持不变的接口前缀

前端不改 `MyMCP` 页面 API 语义，仍然使用：

- `GET /api/my-mcp`
- `GET /api/my-mcp/{client_key}`
- `POST /api/my-mcp`
- `PUT /api/my-mcp/{client_key}`
- `DELETE /api/my-mcp/{client_key}`
- `PATCH /api/my-mcp/{client_key}/toggle`
- `POST /api/my-mcp/{client_key}/test`
- `POST /api/my-mcp/draft-test`
- `POST /api/my-mcp/publish`

变化点只有一个：

- 这些接口由 `market` 服务提供，而不是 `swe` 主服务

### 7.2 发布到市场

`POST /api/my-mcp/publish` 继续保留，作用不变：

- 接收本地 `client_key` 列表
- 读取本地 MCP 配置
- 调用 `market` 内部发布逻辑写入市场

迁移后它不再通过 HTTP 回调另一个市场接口，而是可以直接调用当前 `market` 服务中的 `MarketplaceService.publish_mcp()`。

这样可以去掉本地回环 HTTP 请求，减少一层失败点。

---

## 八、前端影响

### 8.1 前端目标

前端仍然使用 `myMcpApi`，但请求目标服务改为 `market`。

不需要改变：

- 页面布局
- 页面组件拆分
- 弹窗交互
- 列表与详情展示逻辑

### 8.2 前端需要同步调整的点

- `myMcpApi` 请求地址要对准 `market` 服务
- 错误提示继续展示真实后端错误
- “上架”弹窗仍调用 `/api/my-mcp/publish`

本期不重写前端状态管理。

---

## 九、兼容与清理

### 9.1 `swe` 侧清理

迁移完成后：

- 删除 `src/swe/app/routers/my_mcp.py`
- 从 `swe` 主服务路由注册中移除 `my_mcp`
- 删除仅为 `my_mcp.py` 服务的冗余引用

### 9.2 兼容策略

本期不保留双写或双路由兼容。

即：

- 一旦 `market` 的 `my_mcp` 路由切换完成
- `swe` 的 `my_mcp` 立即删除

这样可以避免两套入口同时存在导致行为漂移。

---

## 十、风险与约束

### 10.1 风险

1. `market` 服务缺少 `workspace` 和 `multi_agent_manager`，必须补齐最小可用的配置定位和 reload 能力。
2. 原 `my_mcp.py` 中部分 import 路径位于 `swe.app`，迁移后需要替换导入路径。
3. 删除 `swe` 路由后，任何还在请求旧服务的前端调用都会直接失效，因此前端切换必须与后端迁移同步完成。

### 10.2 已知取舍

- 为了保持行为一致，本次允许 `market` 直接依赖 `swe` 内部模块。
- 本次不追求服务边界纯净，优先保证迁移低风险和逻辑复用。
- 本次不抽象独立的共享 MCP 管理库。

---

## 十一、验收标准

迁移完成后，满足以下条件即视为通过：

1. `MyMCP` 页面所有功能均可正常工作，且后端请求全部由 `market` 服务承接。
2. 用户本地 `agent.json` 中的 `mcp.clients` 仍按原结构保存。
3. 创建、编辑、删除、启停后，目标 agent 的 MCP 行为与迁移前一致。
4. 草稿测试和详情测试连接行为与迁移前一致。
5. 上架到市场行为与迁移前一致。
6. `swe` 主服务中不再保留 `my_mcp.py` 路由实现。

---

## 十二、非目标

以下内容不在本次范围：

- 重构 `swe` 与 `market` 的整体服务边界
- 提炼独立共享库
- 重做 `MyMCP` 前端页面结构
- 重做市场 MCP 的上传、分发、删除语义
- 修改 MCP 数据模型或市场存储格式

