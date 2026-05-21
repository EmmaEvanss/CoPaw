# 租户、应用、来源、管理员关系及目录层级深度分析报告

**调查日期**: 2026-05-04
**最近更新**: 2026-05-17（已按 `scope_id` 统一运行时隔离语义修订）
**调查方式**: 基于实际代码文件分析（禁止猜测和假设）

---

## 一、核心概念定义与关系

### 1.1 租户 (Tenant)

**定义来源**: `src/swe/app/middleware/tenant_identity.py:128`

```python
tenant_id = request.headers.get("X-Tenant-Id")
```

**关键特性**:
- 通过 HTTP Header `X-Tenant-Id` 传递
- 默认租户标识为 `"default"`
- 每个租户拥有独立的工作目录和数据隔离

**运行时 scope 解析**（来源：`src/swe/config/context.py`）：

```python
def resolve_effective_tenant_id(tenant_id: str, source_id: str | None) -> str:
    return resolve_runtime_tenant_id(tenant_id, source_id) or tenant_id
```

### 1.2 来源 (Source)

**定义来源**: `src/swe/config/context.py:31-35`

```python
current_source_id: ContextVar[str | None] = ContextVar("current_source_id", default=None)
```

**关键特性**:
- 通过 HTTP Header `X-Source-Id` 传递
- **对所有租户统一生效**：当 `tenant_id` 与 `source_id` 同时存在时，
  运行时目录、Provider、本地缓存和临时状态都会进入独立 `scope_id`
- `default_{source_id}` 仅保留为模板目录命名语义，不再代表运行时 tenant 目录

### 1.3 来源到租户的转换机制（iframe 嵌入场景）

**前端接收流程**（来源：`console/src/utils/iframeMessage.ts:144-162`）：

```typescript
async function handleUserDataMessage(message: IframeUserDataMessage, origin: string) {
  store.setContext({
    userId: message.data.sapId ?? null,      // sapId 作为 userId
    source: message.data.source ?? null,     // source 作为来源标识
    isSuperManager: toBoolean(message.data.isSuperManager),
    manager: toBoolean(message.data.manager),
    ...
  });
}
```

**关键发现**：**来源不会转换为租户**！

前端构建请求 headers 时（来源：`console/src/api/authHeaders.ts:58-60`）：

```typescript
const userId = getUserId();  // 从 iframe context 获取 sapId
headers["X-User-Id"] = userId;
headers["X-Tenant-Id"] = userId;  // X-Tenant-Id 与 X-User-Id 保持一致！
headers["X-Source-Id"] = iframeContext.source || DEFAULT_SOURCE_ID;
```

**结论**：
- `sapId`（用户 SAP ID）直接作为 `X-Tenant-Id` 使用
- `source` 仅作为 `X-Source-Id` header 传递，用于数据隔离和模板选择
- **租户 = 用户**（在 iframe 嵌入场景下）

### 1.4 用户 (User)

**传递方式**: HTTP Header `X-User-Id`

**用户列表确认机制**：通过运行时 tracing 数据动态确定，详见第五节。

### 1.5 管理员 (Admin)

**前端来源**（来源：`console/src/types/iframe.ts:60-63`）：

```typescript
interface IframeUserDataMessage {
  data: {
    isSuperManager?: boolean | string;  // 超级管理员（父窗口传递）
    manager?: boolean | string;          // 普通管理员（父窗口传递）
    ...
  };
}
```

**关键发现**：管理员身份由**外部父系统（iframe 父窗口）**通过 postMessage 传递，SWE 系统内部不定义！

**前端权限使用**（来源：`console/src/layouts/Header.tsx:28-98`）：

```typescript
const isSuperManager = useIframeStore((state) => state.isSuperManager);
// 当 isSuperManager 为 true 时，显示用户选择下拉框，允许切换查看其他用户
{isSuperManager && (
  <Select value={userId} onChange={handleUserChange} ... />
)}
```

**后端权限验证**（来源：`market/src/market/app/routers/mcp_market.py:29-32`）：

```python
def _require_manager(x_manager: Optional[str]) -> None:
    """校验管理员权限。"""
    if x_manager != "true":
        raise HTTPException(status_code=403, detail="Manager access required")
```

**前端发送管理员标识**（来源：`console/src/api/modules/marketMcp.ts:97,122`）：

```typescript
headers: new Headers({
  "X-Manager": "true",  // 管理员操作时发送此 header
  ...
})
```

**结论**：
- 管理员身份由外部系统决定（iframe 父窗口传递）
- SWE 主服务**没有管理员权限验证**
- Market 服务通过 `X-Manager` header 验证管理员权限
- `isSuperManager` 在前端用于显示用户切换功能

---

## 二、前端分发逻辑分析

### 2.1 分发租户列表获取

**前端调用**（来源：`console/src/pages/Market/MCPDistributeModal.tsx:43-54`）：

```typescript
void api.listMCPDistributionTenants().then((result) => {
  setTenantIds(result.tenant_ids || []);
});
```

**后端实现**（来源：`src/swe/app/routers/mcp.py:480-489`）：

```python
@router.get("/distribution/tenants")
async def list_mcp_distribution_tenants(request: Request):
    """Return all tenants belonging to the current source_id."""
    return MCPDistributionTenantListResponse(
        tenant_ids=await list_logical_tenant_ids(
            _request_source_id(request),
            source_filter=True,  # 启用 source 过滤
        ),
    );
```

**核心逻辑**（来源：`src/swe/config/utils.py:866-879`）：

```python
if source_filter:
    store = get_tenant_init_source_store()
    if store is None or not source_id:
        return []
    rows = await store.get_by_source(source_id)
    return sorted(tid for tid in {row["tenant_id"] for row in rows} if tid != "default")
```

**数据来源**：从 `swe_tenant_init_source` 数据库表查询，按 `source_id` 过滤。

### 2.2 能否跨应用分发？

**答案：不能跨应用（跨 source）分发！**

原因：
1. 分发租户列表通过 `source_filter=True` 查询，只返回属于当前 `source_id` 的租户
2. 数据库查询：`WHERE source_id = ?`，严格按来源过滤
3. 前端无法选择其他 `source_id` 的租户

**分发范围**：仅限当前 `source_id`（来源/应用）下的租户。

### 2.3 分发执行流程

**前端请求**（来源：`console/src/api/modules/marketMcp.ts:107-130`）：

```typescript
distributeMCP: async (sourceId, itemId, userId, userName, data) => {
  const opts: RequestInit = {
    method: "POST",
    headers: new Headers({
      "X-Source-Id": resolvedSourceId,
      "X-User-Id": userId,
      "X-Manager": "true",  // 管理员标识
    }),
    body: JSON.stringify(data),  // { target_tenant_ids: [...], overwrite: true }
  };
  return request(`/market/mcp/${itemId}/distribute`, opts);
}
```

**后端验证与执行**（来源：`market/src/market/app/routers/mcp_market.py:194-231`）：

```python
@router.post("/market/mcp/{item_id}/distribute")
async def distribute_mcp(item_id, req, request, x_source_id, x_manager, x_user_id, x_user_name):
    source_id = require_source_id(x_source_id)
    _require_manager(x_manager)  # 必须是管理员
    result = await svc.distribute_mcp(source_id, item_id, operator_id, operator_name, req)
    return result
```

---

## 三、目录层级划分

### 3.1 核心目录

```text
~/.swe/                                     # WORKING_DIR
├── default/                                # 默认逻辑租户 / 模板根
│   ├── config.json
│   ├── workspaces/default/
│   │   ├── agent.json, chats.json, jobs.json
│   │   ├── sessions/, memory/, skills/
│   └── skill_pool/
├── default_ruice/                          # source 模板目录（初始化模板，不是 runtime tenant）
├── <default>.<ruice>/                      # default + ruice 的运行时目录
└── <sapId>.<ruice>/                        # iframe 用户 + ruice 的运行时目录

~/.swe.secret/                              # SECRET_DIR
├── default/providers/                      # 默认模板 Provider 配置
├── default_ruice/providers/                # source 模板 Provider 配置
└── <tenant>.<source>/providers/            # 运行时 Provider 隔离目录
```

### 3.2 租户-来源-目录映射

| tenant_id | source_id | effective_tenant_id | 工作目录 |
|-----------|-----------|---------------------|----------|
| `default` | `None` | `default` | `~/.swe/default/` |
| `default` | `ruice` | `<default>.<ruice>` | `~/.swe/<default>.<ruice>/` |
| `{sapId}` | `ruice` | `<sapId>.<ruice>` | `~/.swe/<sapId>.<ruice>/` |

**关键规则**：只要请求进入 tenant-scoped runtime，`source_id` 就会参与运行时 scope 计算；非默认租户也不再复用裸 `tenant_id` 目录。

### 3.3 历史裸目录迁移

当历史环境仍保留以下旧目录时：

```text
~/.swe/<tenant-id>/
~/.swe.secret/<tenant-id>/
```

且这些目录实际属于某个已知 `source_id`，可使用脚本：

```bash
python scripts/migrate_tenant_scope_dirs.py \
  --tenant-id <tenant-id> \
  --source-id <source-id> \
  --dry-run
```

如需按同一 `source_id` 批量迁移多个租户，可使用：

```bash
python scripts/migrate_tenant_scope_dirs.py \
  --tenant-ids tenant-a,tenant-b \
  --source-id <source-id> \
  --dry-run
```

批量模式会先对整批租户执行预检查，只要任一目标目录已存在就整批拒绝，
避免出现部分租户先迁移、后续租户失败的半完成状态。确认输出无误后移除
`--dry-run` 执行正式迁移。脚本会把目录移动到
`<encoded-tenant>.<encoded-source>`，并同步修正工作目录内 JSON 配置
引用的旧绝对路径。`default_<source>` 仍然只是模板目录，不能通过该脚本
当作运行时租户目录迁移。

如果需要把已有 canonical scope ID 反向解析回逻辑身份，可使用：

```bash
python scripts/decode_scope_ids.py \
  --scope-id dGVuYW50LWE.c291cmNlLWE
```

或批量解析：

```bash
python scripts/decode_scope_ids.py \
  --scope-ids dGVuYW50LWE.c291cmNlLWE,ZGVmYXVsdA.cnVpY2U
```

该脚本只接受当前 canonical 格式，不兼容历史 `scope.v1.*` 输入。

---

## 四、用户确认机制

### 4.1 数据存储

用户列表通过运行时 tracing 数据动态确定，存储在数据库：

| 表名 | 用途 | 隔离键 |
|------|------|--------|
| `swe_tracing_traces` | 会话级数据 | `source_id`, `user_id` |
| `swe_tracing_spans` | 事件级数据 | `source_id`, `user_id` |

### 4.2 用户列表查询

**来源**：`src/swe/tracing/store.py:780-878`

```python
async def get_users_with_stats(source_id, page, page_size, user_id, ...):
    where_clauses = ["source_id = %s"]
    where_clauses.append("user_id != 'default'")  # 排除测试用户
    query = "SELECT DISTINCT user_id FROM swe_tracing_traces WHERE ..."
```

### 4.3 用户详细信息

通过外部 API 查询（来源：`src/swe/app/routers/user_info.py`），地址由 `USER_INFO_API_URL` 环境变量配置。

---

## 五、iframe 嵌入完整流程图

```text
父系统 iframe 嵌入 SWE
    ↓
postMessage 发送 USER_DATA
    ├── sapId: 用户 SAP ID
    ├── source: 来源标识（如 "ruice"）
    ├── isSuperManager: 超管标识
    └── manager: 管理员标识
    ↓
iframeMessage.ts 接收并存储到 iframeStore
    ├── userId = sapId
    ├── source = source
    └── isSuperManager, manager
    ↓
authHeaders.ts 构建 HTTP headers
    ├── X-User-Id = sapId
    ├── X-Tenant-Id = sapId  (租户 = 用户!)
    ├── X-Source-Id = source
    └── X-Manager = "true" (管理员操作时)
    ↓
后端 TenantIdentityMiddleware 提取 headers
    ↓
resolve_runtime_tenant_id(tenant_id, source_id)
    ├── tenant_id + source_id → encode_scope_id(...) = scope_id
    └── source_id 缺失 → 仅保留逻辑 tenant_id（用于非 scoped 场景）
    ↓
租户工作目录: ~/.swe/<tenant>.<source>/
```

---

## 六、关键代码路径索引

| 功能 | 文件路径 | 关键行号 |
|------|----------|----------|
| iframe 消息接收 | `console/src/utils/iframeMessage.ts` | 144-162 |
| iframe 上下文存储 | `console/src/stores/iframeStore.ts` | 71-92 |
| Headers 构建 | `console/src/api/authHeaders.ts` | 58-84 |
| 管理员类型定义 | `console/src/types/iframe.ts` | 60-63 |
| 超管用户切换 UI | `console/src/layouts/Header.tsx` | 28-110 |
| 分发租户列表 | `src/swe/app/routers/mcp.py` | 480-489 |
| 分发逻辑查询 | `src/swe/config/utils.py` | 866-879 |
| 后端管理员验证 | `market/src/market/app/routers/mcp_market.py` | 29-32 |
| 分发 API | `market/src/market/app/routers/mcp_market.py` | 194-231 |
| 前端分发弹窗 | `console/src/pages/Market/MCPDistributeModal.tsx` | 43-128 |
| 用户列表查询 | `src/swe/tracing/store.py` | 780-878 |

---

## 七、总结

### 核心关系

| 概念 | 来源 | 转换关系 |
|------|------|----------|
| 租户 | `X-Tenant-Id` header | iframe 场景：`sapId` 直接作为租户 |
| 来源 | `X-Source-Id` header | 对所有 tenant-scoped runtime 生效，参与编码 `scope_id` |
| 用户 | `X-User-Id` header | iframe 场景：与租户相同（`sapId`） |
| 管理员 | iframe postMessage | 外部系统决定，通过 `X-Manager` header 传递 |

### 分发限制

- **不能跨应用分发**：分发仅限当前 `source_id` 下的租户
- **管理员权限验证**：仅在 Market 服务中通过 `X-Manager` header 验证
- **SWE 主服务无管理员验证**：权限控制依赖 Market 服务

### iframe 场景关键点

1. `sapId` 直接作为 `X-Tenant-Id`，**无 source → tenant 转换**
2. 管理员身份由外部父系统决定
3. 用户列表通过 tracing 数据动态查询

---

**报告撰写**: 基于实际代码文件分析，无猜测假设。
