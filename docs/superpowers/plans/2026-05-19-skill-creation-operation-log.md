# 技能创建操作日志实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现技能创建操作日志记录功能，Agent 通过 skill_creator 创建技能后上报日志。

**Architecture:** 在 market 服务新增 `/market/skills/operation-log` 端点，skill_creator SKILL.md 增加上报步骤，采用"失败忽略"策略确保性能影响最小。

**Tech Stack:** FastAPI, MySQL, Python

---

## 文件结构

| 文件 | 操作 | 说明 |
|------|------|------|
| `market/src/market/app/routers/skills_browse.py` | Modify | 新增操作日志端点 |
| `skill_creator/SKILL.md` | Modify | 增加步骤 6：上报操作日志 |
| `market/tests/unit/marketplace/test_skills_browse.py` | Modify | 新增测试 |

---

### Task 1: 新增操作日志 API 端点

**Files:**
- Modify: `market/src/market/app/routers/skills_browse.py`
- Test: `market/tests/unit/marketplace/test_skills_browse.py`

- [ ] **Step 1: 编写失败测试**

在 `market/tests/unit/marketplace/test_skills_browse.py` 文件末尾添加：

```python
def test_log_skill_operation_returns_200(tmp_path):
    """测试操作日志上报端点返回成功。"""
    from fastapi import FastAPI
    from market.app.routers.skills_browse import router
    from market.marketplace.service import MarketplaceService
    from market.database.connection import DatabaseConnection
    from unittest.mock import AsyncMock

    mock_db = AsyncMock(spec=DatabaseConnection)
    mock_db.is_connected = True
    mock_db.execute = AsyncMock()

    svc = MarketplaceService(
        db=mock_db,
        marketplace_root=tmp_path / "market",
        swe_root=tmp_path / "swe",
    )
    app = FastAPI()
    app.state.marketplace = svc
    app.include_router(router, prefix="/api")

    client = TestClient(app)
    resp = client.post(
        "/api/market/skills/operation-log",
        headers={
            "X-Source-Id": "console",
            "X-User-Id": "user123",
        },
        json={
            "operation": "create",
            "item_type": "skill",
            "item_name": "my_new_skill",
        },
    )
    assert resp.status_code == 200
    assert resp.json() == {"success": True}
    mock_db.execute.assert_called_once()


def test_log_skill_operation_missing_user_id_returns_400(tmp_path):
    """测试缺少 X-User-Id 返回 400。"""
    from fastapi import FastAPI
    from market.app.routers.skills_browse import router
    from market.marketplace.service import MarketplaceService
    from market.database.connection import DatabaseConnection
    from unittest.mock import AsyncMock

    mock_db = AsyncMock(spec=DatabaseConnection)
    mock_db.is_connected = False

    svc = MarketplaceService(
        db=mock_db,
        marketplace_root=tmp_path / "market",
        swe_root=tmp_path / "swe",
    )
    app = FastAPI()
    app.state.marketplace = svc
    app.include_router(router, prefix="/api")

    client = TestClient(app)
    resp = client.post(
        "/api/market/skills/operation-log",
        headers={"X-Source-Id": "console"},
        json={
            "operation": "create",
            "item_type": "skill",
            "item_name": "my_new_skill",
        },
    )
    assert resp.status_code == 400


def test_log_skill_operation_db_failure_returns_success(tmp_path):
    """测试数据库写入失败仍返回成功（失败忽略策略）。"""
    from fastapi import FastAPI
    from market.app.routers.skills_browse import router
    from market.marketplace.service import MarketplaceService
    from market.database.connection import DatabaseConnection
    from unittest.mock import AsyncMock

    mock_db = AsyncMock(spec=DatabaseConnection)
    mock_db.is_connected = True
    mock_db.execute = AsyncMock(side_effect=Exception("DB error"))

    svc = MarketplaceService(
        db=mock_db,
        marketplace_root=tmp_path / "market",
        swe_root=tmp_path / "swe",
    )
    app = FastAPI()
    app.state.marketplace = svc
    app.include_router(router, prefix="/api")

    client = TestClient(app)
    resp = client.post(
        "/api/market/skills/operation-log",
        headers={
            "X-Source-Id": "console",
            "X-User-Id": "user123",
        },
        json={
            "operation": "create",
            "item_type": "skill",
            "item_name": "my_new_skill",
        },
    )
    # 失败忽略：即使 DB 写入失败，仍返回成功
    assert resp.status_code == 200
    assert resp.json() == {"success": True}
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd market && python -m pytest tests/unit/marketplace/test_skills_browse.py::test_log_skill_operation_returns_200 -v`

Expected: FAIL with "404 Not Found" 或类似路由未定义错误

- [ ] **Step 3: 实现操作日志端点**

在 `market/src/market/app/routers/skills_browse.py` 文件末尾添加：

```python
# -----------------------------------------------------------
# 操作日志上报端点
# -----------------------------------------------------------


class OperationLogRequest(BaseModel):
    """操作日志上报请求体。"""

    operation: str = Field(..., description="操作类型: create/edit/delete")
    item_type: str = Field(default="skill", description="条目类型: skill/mcp")
    item_name: str = Field(..., description="条目名称")
    user_name: Optional[str] = Field(default=None, description="用户名称")
    bbk_id: Optional[str] = Field(default=None, description="机构ID")


@router.post("/market/skills/operation-log")
async def log_skill_operation(
    request: Request,
    body: OperationLogRequest,
    x_source_id: Optional[str] = Header(default=None, alias="X-Source-Id"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
):
    """上报技能操作日志。

    用于 Agent 通过 skill_creator 创建技能后记录操作日志。
    采用失败忽略策略，写入失败不影响业务。
    """
    source_id = require_source_id(x_source_id)
    if not x_user_id:
        raise HTTPException(
            status_code=400,
            detail="X-User-Id header is required",
        )

    svc = request.app.state.marketplace
    user_name = body.user_name or x_user_id

    if svc.db.is_connected:
        try:
            await svc.db.execute(
                """
                INSERT INTO swe_user_item_operation_logs
                    (source_id, user_id, user_name, operation,
                     item_type, item_name)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    source_id,
                    x_user_id,
                    user_name,
                    body.operation,
                    body.item_type,
                    body.item_name,
                ),
            )
        except Exception as e:
            logger.warning("Failed to log operation: %s", e)

    return {"success": True}
```

同时在文件顶部的 imports 中添加：

```python
from pydantic import BaseModel, Field
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd market && python -m pytest tests/unit/marketplace/test_skills_browse.py::test_log_skill_operation_returns_200 tests/unit/marketplace/test_skills_browse.py::test_log_skill_operation_missing_user_id_returns_400 tests/unit/marketplace/test_skills_browse.py::test_log_skill_operation_db_failure_returns_success -v`

Expected: All PASS

- [ ] **Step 5: 提交**

```bash
git add market/src/market/app/routers/skills_browse.py market/tests/unit/marketplace/test_skills_browse.py
git commit -m "feat(market): add operation-log endpoint for skill creation logging"
```

---

### Task 2: 修改 skill_creator SKILL.md

**Files:**
- Modify: `skill_creator/SKILL.md`

- [ ] **Step 1: 修改文档增加步骤 6**

在 `skill_creator/SKILL.md` 文件的步骤 5 后（约第 263 行之后），添加新的步骤 6：

```markdown
### 步骤 6：上报操作日志

技能创建完成后，需要上报操作日志以记录此次创建行为。

使用 `execute_shell_command` 调用日志上报 API：

```bash
curl -X POST "http://localhost:8000/market/skills/operation-log" \
  -H "Content-Type: application/json" \
  -H "X-Source-Id: console" \
  -H "X-User-Id: <当前用户ID>" \
  -d '{
    "operation": "create",
    "item_type": "skill",
    "item_name": "<创建的技能名称>",
    "user_name": "<当前用户名称>"
  }'
```

**注意**：
- 日志上报失败不影响技能创建结果，API 会返回 `{"success": true}` 即使写入失败
- 如果 API 调用失败，记录警告即可，无需重试
- 确保在技能文件生成完成后执行此步骤
```

同时修改步骤 5 的最后一行（第 263 行），将"生成完成后进行二次检查"改为：

```markdown
当以上步骤完成后，你需要将技能相关的所有文件通过`execute_shell_command`生成在用户工作目录中，并在生成完成后进行二次检查。检查无误后，执行步骤 6 上报操作日志。
```

- [ ] **Step 2: 验证文档格式正确**

Run: `cat skill_creator/SKILL.md | head -n 280`

Expected: 能看到新增的步骤 6 内容

- [ ] **Step 3: 提交**

```bash
git add skill_creator/SKILL.md
git commit -m "docs(skill_creator): add step 6 for operation log reporting"
```

---

### Task 3: 验证整体功能

- [ ] **Step 1: 运行全部相关测试**

Run: `cd market && python -m pytest tests/unit/marketplace/test_skills_browse.py -v`

Expected: All PASS

- [ ] **Step 2: 手动验证 API 可访问**

启动 market 服务后，执行：

```bash
curl -X POST "http://localhost:8000/market/skills/operation-log" \
  -H "Content-Type: application/json" \
  -H "X-Source-Id: console" \
  -H "X-User-Id: test_user" \
  -d '{
    "operation": "create",
    "item_type": "skill",
    "item_name": "test_skill"
  }'
```

Expected: `{"success": true}`

- [ ] **Step 3: 最终提交**

```bash
git add docs/superpowers/specs/2026-05-19-skill-creation-operation-log-design.md
git commit -m "docs: add skill creation operation log design spec"
```

---

## Self-Review

**1. Spec coverage:**
- [x] API 端点设计 → Task 1
- [x] skill_creator 文档修改 → Task 2
- [x] 失败忽略策略 → Task 1 Step 3
- [x] 测试验证 → Task 1 & Task 3

**2. Placeholder scan:**
- 无 TBD/TODO
- 无"add validation"等模糊描述
- 所有代码步骤都有完整实现代码

**3. Type consistency:**
- OperationLogRequest 的字段名与现有日志插入语句一致
- API 路径 `/market/skills/operation-log` 与测试中使用的路径一致