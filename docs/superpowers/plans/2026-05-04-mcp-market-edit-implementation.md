# MCP 市场编辑能力 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为应用市场 `MCP` tab 增加管理员可用的“编辑市场元数据”能力，只允许修改中文名称、描述、使用指引和可见机构，不允许修改连接器配置或上传文件。

**Architecture:** 前端在现有 `MarketSkills -> MCPCard / MCPDetailDrawer` 入口上增加 `编辑` 按钮，并新增独立的 `MCPEditModal`。后端在 `market` 服务新增 MCP 元数据更新接口与 service 方法，只更新条目元数据并刷新 `updated_at`，不改变 `config`、`item_id`、`created_at` 和 `version`。

**Tech Stack:** React + Ant Design、TypeScript、FastAPI、Pydantic、现有 `marketplace` service/fs/index 体系、Vitest、Python `py_compile`

---

## 文件结构

**前端修改**

- Modify: `console/src/pages/Market/MarketSkills.tsx`
  - 增加编辑状态、打开编辑弹窗、保存成功后刷新列表/详情
- Modify: `console/src/pages/Market/MCPCard.tsx`
  - 在列表卡片动作区增加 `编辑` 按钮，仅管理员可见
- Modify: `console/src/pages/Market/MCPDetailDrawer.tsx`
  - 在详情页动作区增加 `编辑` 按钮，仅管理员可见
- Create: `console/src/pages/Market/MCPEditModal.tsx`
  - 独立元数据编辑弹窗
- Modify: `console/src/api/modules/marketMcp.ts`
  - 新增调用 `PUT /market/mcp/{item_id}/metadata`
- Modify: `console/src/api/types/marketMcp.ts`
  - 新增编辑请求/响应类型
- Modify: `console/src/pages/Market/MarketMCP.test.tsx`
  - 增加编辑按钮展示、编辑弹窗提交与刷新断言

**后端修改**

- Modify: `market/src/market/marketplace/schemas.py`
  - 新增 MCP 元数据更新请求 schema
- Modify: `market/src/market/marketplace/service.py`
  - 新增元数据更新 service
- Modify: `market/src/market/app/routers/mcp_market.py`
  - 新增 `PUT /market/mcp/{item_id}/metadata`

**文档/验证**

- Verify only: `docs/superpowers/specs/2026-05-04-mcp-market-edit-design.md`

---

### Task 1: 补后端 schema 与 service

**Files:**
- Modify: `market/src/market/marketplace/schemas.py`
- Modify: `market/src/market/marketplace/service.py`
- Test: `venv\\Scripts\\python.exe -m py_compile market\\src\\market\\marketplace\\schemas.py market\\src\\market\\marketplace\\service.py`

- [ ] **Step 1: 在 schema 中新增元数据更新请求模型**

在 `market/src/market/marketplace/schemas.py` 增加一个仅包含元数据字段的请求模型，字段与 spec 保持一致：

```python
class UpdateMarketMCPMetadataRequest(BaseModel):
    chinese_name: str | None = None
    description: str | None = None
    guidance: str | None = None
    bbk_ids: list[str] = Field(default_factory=list)
```

要求：

- 不包含 `config`
- 不包含 `name`
- 不包含 `client_key`
- 不包含 `version`

- [ ] **Step 2: 运行编译检查，确认 schema 可加载**

Run:

```powershell
venv\Scripts\python.exe -m py_compile market\src\market\marketplace\schemas.py
```

Expected:

```text
无输出，退出码 0
```

- [ ] **Step 3: 在 service 中新增元数据更新方法**

在 `market/src/market/marketplace/service.py` 增加独立方法，只更新元数据，不改配置：

```python
def update_mcp_metadata(
    self,
    *,
    source_id: str,
    item_id: str,
    chinese_name: str | None,
    description: str | None,
    guidance: str | None,
    bbk_ids: list[str],
) -> MCPMarketItem:
    item = self.get_mcp_item(source_id=source_id, item_id=item_id)
    if item is None:
        raise FileNotFoundError(f"MCP item '{item_id}' not found")

    updated = item.model_copy(
        update={
            "chinese_name": chinese_name or "",
            "description": description or "",
            "guidance": guidance or "",
            "bbk_ids": bbk_ids,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    )
    self.save_mcp_item(source_id=source_id, item=updated)
    return updated
```

实现要求：

- 保留 `config`
- 保留 `version`
- 保留 `created_at`
- 保留 `item_id`

- [ ] **Step 4: 运行编译检查，确认 service 可加载**

Run:

```powershell
venv\Scripts\python.exe -m py_compile market\src\market\marketplace\service.py
```

Expected:

```text
无输出，退出码 0
```

- [ ] **Step 5: Commit**

```bash
git add market/src/market/marketplace/schemas.py market/src/market/marketplace/service.py
git commit -m "feat(market): add mcp metadata update service"
```

### Task 2: 暴露后端元数据更新接口

**Files:**
- Modify: `market/src/market/app/routers/mcp_market.py`
- Test: `venv\\Scripts\\python.exe -m py_compile market\\src\\market\\app\\routers\\mcp_market.py`

- [ ] **Step 1: 新增路由请求导入**

在 `market/src/market/app/routers/mcp_market.py` 中导入新增 schema 和现有 manager/source 校验依赖，确保路由可直接复用当前 MCP 市场上下文。

需要新增的导入形态：

```python
from market.marketplace.schemas import UpdateMarketMCPMetadataRequest
```

- [ ] **Step 2: 新增元数据更新路由**

在 MCP 市场 router 中新增：

```python
@router.put("/mcp/{item_id}/metadata", response_model=MarketMCPDetail)
async def update_market_mcp_metadata(
    item_id: str,
    payload: UpdateMarketMCPMetadataRequest,
    request: Request,
):
    ensure_manager(request)
    source_id = get_source_id_for_market(request) or "default"
    try:
        item = marketplace_service.update_mcp_metadata(
            source_id=source_id,
            item_id=item_id,
            chinese_name=payload.chinese_name,
            description=payload.description,
            guidance=payload.guidance,
            bbk_ids=payload.bbk_ids,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"MCP item '{item_id}' not found")
    return build_market_mcp_detail(item)
```

要求：

- 权限校验与当前删除/上传链路保持一致
- `source_id` 缺失时继续使用 `"default"` 兜底
- 返回结构与现有 MCP 详情一致

- [ ] **Step 3: 运行编译检查**

Run:

```powershell
venv\Scripts\python.exe -m py_compile market\src\market\app\routers\mcp_market.py
```

Expected:

```text
无输出，退出码 0
```

- [ ] **Step 4: 手工自检返回结构与现有详情字段一致**

检查点：

- 路由返回的对象仍包含：
  - `item_id`
  - `name`
  - `config`
  - `version`
  - `created_at`
  - `updated_at`
  - `chinese_name`
  - `description`
  - `guidance`
  - `bbk_ids`

Expected:

```text
无需新增第二套 detail response 结构
```

- [ ] **Step 5: Commit**

```bash
git add market/src/market/app/routers/mcp_market.py
git commit -m "feat(market): add mcp metadata update endpoint"
```

### Task 3: 补前端 API 与类型

**Files:**
- Modify: `console/src/api/types/marketMcp.ts`
- Modify: `console/src/api/modules/marketMcp.ts`
- Test: `npm run test:run -- src/pages/Market/MarketMCP.test.tsx`

- [ ] **Step 1: 在 types 中新增编辑请求类型**

在 `console/src/api/types/marketMcp.ts` 增加：

```ts
export interface UpdateMarketMCPMetadataRequest {
  chinese_name?: string;
  description?: string;
  guidance?: string;
  bbk_ids: string[];
}
```

并确认现有 `MarketMCPDetail` 已包含以下字段，若缺失则补齐：

```ts
chinese_name?: string;
description?: string;
guidance?: string;
bbk_ids: string[];
```

- [ ] **Step 2: 在 API 模块中新增更新方法**

在 `console/src/api/modules/marketMcp.ts` 增加：

```ts
async updateMarketMCPMetadata(
  sourceId: string,
  itemId: string,
  payload: UpdateMarketMCPMetadataRequest,
  userId: string,
  userName: string,
): Promise<MarketMCPDetail> {
  return request<MarketMCPDetail>(`/market/mcp/${itemId}/metadata`, {
    method: "PUT",
    headers: buildAuthHeaders(sourceId, userId, userName),
    body: JSON.stringify(payload),
  });
}
```

要求：

- 请求头与当前市场 MCP 其它接口保持一致
- 不用 `FormData`
- 不走上传接口

- [ ] **Step 3: 运行现有 MCP 市场测试**

Run:

```powershell
npm run test:run -- src/pages/Market/MarketMCP.test.tsx
```

Expected:

```text
现有测试继续通过，若有新增断言失败则进入后续任务修正
```

- [ ] **Step 4: Commit**

```bash
git add console/src/api/types/marketMcp.ts console/src/api/modules/marketMcp.ts
git commit -m "feat(console): add market mcp metadata update api"
```

### Task 4: 新增 MCPEditModal

**Files:**
- Create: `console/src/pages/Market/MCPEditModal.tsx`
- Test: `npm run test:run -- src/pages/Market/MarketMCP.test.tsx`

- [ ] **Step 1: 创建编辑弹窗组件骨架**

新建 `console/src/pages/Market/MCPEditModal.tsx`，使用现有市场页的 Ant Design 体系，暴露如下接口：

```ts
interface MCPEditModalProps {
  open: boolean;
  mcp: MarketMCPDetail | null;
  sourceId: string;
  userId: string;
  userName: string;
  onClose: () => void;
  onSuccess: (detail: MarketMCPDetail) => void;
}
```

组件外层结构：

```tsx
<Modal open={open} title="编辑 MCP 信息" onCancel={onClose} onOk={handleSubmit}>
  ...
</Modal>
```

- [ ] **Step 2: 实现只读英文名称与可编辑元数据字段**

在弹窗中放入以下字段：

```tsx
<Form layout="vertical" form={form}>
  <Form.Item label="英文名称">
    <Input value={mcp?.name} readOnly />
  </Form.Item>
  <Form.Item label="中文名称（可选）" name="chinese_name">
    <Input placeholder="请输入中文名称（可选）" />
  </Form.Item>
  <Form.Item label="描述（可选）" name="description">
    <Input.TextArea rows={3} placeholder="请输入描述（可选）" />
  </Form.Item>
  <Form.Item label="使用指引（可选）" name="guidance">
    <Input.TextArea rows={4} placeholder="请输入使用指引（可选）" />
  </Form.Item>
</Form>
```

并增加说明文案：

```tsx
<Alert
  type="info"
  showIcon
  message="仅支持修改展示信息；如需修改连接器配置，请使用“上传连接器”重新上传覆盖。"
/>
```

- [ ] **Step 3: 接入可见机构选择与提交逻辑**

沿用当前市场页已有机构选择方式，把 `bbk_ids` 放进表单并在提交时调用：

```ts
await marketMcpApi.updateMarketMCPMetadata(sourceId, mcp.item_id, payload, userId, userName)
```

提交成功后：

```ts
message.success("保存成功");
onSuccess(detail);
```

失败时：

```ts
message.error(error instanceof Error ? error.message : "保存失败");
```

- [ ] **Step 4: 运行现有 MCP 市场测试**

Run:

```powershell
npm run test:run -- src/pages/Market/MarketMCP.test.tsx
```

Expected:

```text
现有测试通过；若新增编辑相关测试尚未写入，可先保持基线稳定
```

- [ ] **Step 5: Commit**

```bash
git add console/src/pages/Market/MCPEditModal.tsx
git commit -m "feat(console): add mcp edit modal"
```

### Task 5: 接入列表页与详情页编辑入口

**Files:**
- Modify: `console/src/pages/Market/MCPCard.tsx`
- Modify: `console/src/pages/Market/MCPDetailDrawer.tsx`
- Modify: `console/src/pages/Market/MarketSkills.tsx`
- Test: `npm run test:run -- src/pages/Market/MarketMCP.test.tsx`

- [ ] **Step 1: 扩展列表卡片 props 并增加编辑按钮**

在 `console/src/pages/Market/MCPCard.tsx` 中扩展 props：

```ts
interface MCPCardProps {
  mcp: MarketMCPItem;
  onOpenDetail: () => void;
  onDistribute: () => void;
  onEdit?: () => void;
  onDelete: () => void;
  canEdit?: boolean;
}
```

在动作区插入：

```tsx
{canEdit ? (
  <Button onClick={onEdit} style={...}>
    编辑
  </Button>
) : null}
```

位置要求：

- 放在 `分发` 和 `删除` 之间

- [ ] **Step 2: 在详情页动作区增加编辑按钮**

在 `console/src/pages/Market/MCPDetailDrawer.tsx` 中扩展 props：

```ts
onEdit?: () => void;
canEdit?: boolean;
```

在右上角动作区插入：

```tsx
{canEdit ? (
  <Button onClick={onEdit} style={{ borderRadius: 10 }}>
    编辑
  </Button>
) : null}
```

- [ ] **Step 3: 在 MarketSkills 中接入编辑状态管理**

在 `console/src/pages/Market/MarketSkills.tsx` 增加状态：

```ts
const [mcpEditModalOpen, setMcpEditModalOpen] = useState(false);
const [editingMCP, setEditingMCP] = useState<MarketMCPDetail | null>(null);
```

增加方法：

```ts
const openMCPEditModal = useCallback(async (target: MarketMCPItem | MarketMCPDetail) => {
  const detail =
    "config" in target ? target : await marketMcpApi.getMarketMCPDetail(sourceId, target.item_id, bbkId);
  setEditingMCP(detail);
  setMcpEditModalOpen(true);
}, [sourceId, bbkId]);
```

并在保存成功后：

```ts
const handleMCPEditSuccess = useCallback(async (detail: MarketMCPDetail) => {
  setMcpEditModalOpen(false);
  setEditingMCP(null);
  await refreshMCP();
  if (selectedMCP?.item_id === detail.item_id) {
    const latest = await marketMcpApi.getMarketMCPDetail(sourceId, detail.item_id, bbkId);
    setSelectedMCP(latest);
  }
}, [refreshMCP, selectedMCP, sourceId, bbkId]);
```

- [ ] **Step 4: 在列表与详情中挂接编辑入口，并仅管理员显示**

列表挂接：

```tsx
<MCPCard
  ...
  canEdit={isManager}
  onEdit={() => openMCPEditModal(mcp)}
/>
```

详情挂接：

```tsx
<MCPDetailDrawer
  ...
  canEdit={isManager}
  onEdit={() => openMCPEditModal(selectedMCP)}
/>
```

并在页面底部挂载：

```tsx
<MCPEditModal
  open={mcpEditModalOpen}
  mcp={editingMCP}
  sourceId={sourceId}
  userId={userId}
  userName={userName}
  onClose={() => {
    setMcpEditModalOpen(false);
    setEditingMCP(null);
  }}
  onSuccess={handleMCPEditSuccess}
/>
```

- [ ] **Step 5: 运行 MCP 市场测试**

Run:

```powershell
npm run test:run -- src/pages/Market/MarketMCP.test.tsx
```

Expected:

```text
列表态与详情态现有测试继续通过
```

- [ ] **Step 6: Commit**

```bash
git add console/src/pages/Market/MCPCard.tsx console/src/pages/Market/MCPDetailDrawer.tsx console/src/pages/Market/MarketSkills.tsx
git commit -m "feat(console): wire mcp edit actions into market page"
```

### Task 6: 增补 MCP 市场前端测试

**Files:**
- Modify: `console/src/pages/Market/MarketMCP.test.tsx`

- [ ] **Step 1: 增加管理员看到编辑按钮的测试**

在 `console/src/pages/Market/MarketMCP.test.tsx` 增加断言：

```tsx
it("管理员在 MCP 列表中可见编辑按钮", async () => {
  renderMarketPage({ isManager: true });
  expect(await screen.findByText("编辑")).toBeInTheDocument();
});
```

- [ ] **Step 2: 增加非管理员看不到编辑按钮的测试**

```tsx
it("非管理员在 MCP 列表中不可见编辑按钮", async () => {
  renderMarketPage({ isManager: false });
  expect(screen.queryByText("编辑")).not.toBeInTheDocument();
});
```

- [ ] **Step 3: 增加编辑弹窗提交后刷新详情的测试**

最小断言即可，重点验证调用链：

```tsx
it("编辑保存成功后刷新列表并更新当前详情", async () => {
  marketMcpApi.updateMarketMCPMetadata = vi.fn().mockResolvedValue(updatedDetail);
  marketMcpApi.getMarketMCPDetail = vi.fn().mockResolvedValue(updatedDetail);
  renderMarketPage({ isManager: true });
  // 打开详情 -> 打开编辑 -> 提交 -> 断言 update 与 detail refresh 被调用
});
```

- [ ] **Step 4: 运行测试并确认通过**

Run:

```powershell
npm run test:run -- src/pages/Market/MarketMCP.test.tsx
```

Expected:

```text
PASS，新增编辑相关断言全部通过
```

- [ ] **Step 5: Commit**

```bash
git add console/src/pages/Market/MarketMCP.test.tsx
git commit -m "test(console): cover market mcp edit flow"
```

### Task 7: 最终验证

**Files:**
- Verify only: `console/src/pages/Market/*`
- Verify only: `market/src/market/app/routers/mcp_market.py`
- Verify only: `market/src/market/marketplace/*`

- [ ] **Step 1: 运行前端 MCP 市场定向测试**

Run:

```powershell
npm run test:run -- src/pages/Market/MarketMCP.test.tsx
```

Expected:

```text
PASS
```

- [ ] **Step 2: 运行后端定向编译检查**

Run:

```powershell
venv\Scripts\python.exe -m py_compile market\src\market\marketplace\schemas.py market\src\market\marketplace\service.py market\src\market\app\routers\mcp_market.py
```

Expected:

```text
无输出，退出码 0
```

- [ ] **Step 3: 手工联调检查**

检查顺序：

```text
1. 管理员打开 应用市场 -> MCP，列表卡片看到 编辑
2. 非管理员打开同页，看不到 编辑
3. 列表页点击 编辑，弹出 MCPEditModal
4. 详情页点击 编辑，弹出 MCPEditModal
5. 修改 中文名称 / 描述 / 使用指引 / 可见机构 后保存成功
6. 列表刷新，详情态同步展示新元数据
7. 版本不变化
8. 测试连接仍可正常工作
9. 分发功能不受影响
```

- [ ] **Step 4: Commit**

```bash
git add console/src/pages/Market/MCPCard.tsx console/src/pages/Market/MCPDetailDrawer.tsx console/src/pages/Market/MarketSkills.tsx console/src/pages/Market/MCPEditModal.tsx console/src/pages/Market/MarketMCP.test.tsx console/src/api/modules/marketMcp.ts console/src/api/types/marketMcp.ts market/src/market/marketplace/schemas.py market/src/market/marketplace/service.py market/src/market/app/routers/mcp_market.py
git commit -m "feat(market): add mcp metadata edit flow"
```

---

## Self-Review

### Spec coverage

- 管理员可见 `编辑`：Task 5、Task 6 覆盖
- 编辑只改元数据：Task 1、Task 2、Task 4 覆盖
- 不改 `config` / `version` / `created_at`：Task 1、Task 2 覆盖
- 列表与详情双入口：Task 5 覆盖
- 保存后刷新列表与详情：Task 5、Task 6 覆盖

### Placeholder scan

- 无 `TODO` / `TBD`
- 每个代码步骤都给出具体代码骨架
- 每个验证步骤都给出明确命令

### Type consistency

- 前端统一使用 `MarketMCPDetail`
- API 方法统一命名为 `updateMarketMCPMetadata`
- 后端 schema 统一命名为 `UpdateMarketMCPMetadataRequest`

