# Tracing 模块添加 user_name 和 bbk_id 字段实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 tracing 模块的 swe_tracing_traces 和 swe_tracing_spans 两张表添加 user_name 和 bbk_id 字段，支持从请求头传递并存储。

**Architecture:** 数据流为 请求头 → 中间件解析 → AgentRequest → Runner 提取 → TraceManager → TraceStore → 数据库。新增字段与现有 user_id 处理方式一致，采用冗余存储策略。

**Tech Stack:** Python (FastAPI, Pydantic, aiomysql), TypeScript (React, Ant Design)

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `scripts/sql/tracing_user_info_migration.sql` | 数据库迁移脚本，添加新字段和索引 |
| `src/swe/app/middleware/tenant_identity.py` | 解析 X-User-Name 和 X-Bbk-Id 请求头 |
| `src/swe/tracing/models.py` | Pydantic 模型添加新字段 |
| `src/swe/tracing/store.py` | 数据库 INSERT/UPDATE SQL 和行转模型方法 |
| `src/swe/tracing/manager.py` | TraceContext 添加新属性，start_trace 添加新参数 |
| `src/swe/agents/hooks/tracing.py` | TracingHook 添加新参数并传递 |
| `src/swe/app/runner/runner.py` | 从 request 提取新字段并传递 |
| `console/src/api/modules/tracing.ts` | 前端 API 类型定义添加新字段 |
| `console/src/pages/Analytics/BusinessOverview/index.tsx` | 前端展示组件 |

---

### Task 1: 数据库迁移脚本

**Files:**
- Create: `scripts/sql/tracing_user_info_migration.sql`

- [ ] **Step 1: 创建迁移脚本**

```sql
-- scripts/sql/tracing_user_info_migration.sql
-- 为 swe_tracing_traces 表添加用户信息字段
ALTER TABLE swe_tracing_traces
ADD COLUMN user_name VARCHAR(128) DEFAULT NULL COMMENT '用户姓名',
ADD COLUMN bbk_id VARCHAR(64) DEFAULT NULL COMMENT '分行编号';

-- 为 swe_tracing_spans 表添加用户信息字段（冗余存储）
ALTER TABLE swe_tracing_spans
ADD COLUMN user_name VARCHAR(128) DEFAULT NULL COMMENT '用户姓名（冗余）',
ADD COLUMN bbk_id VARCHAR(64) DEFAULT NULL COMMENT '分行编号（冗余）';

-- 添加索引以支持按 user_name 和 bbk_id 查询
ALTER TABLE swe_tracing_traces ADD INDEX idx_user_name (user_name);
ALTER TABLE swe_tracing_traces ADD INDEX idx_bbk_id (bbk_id);
ALTER TABLE swe_tracing_spans ADD INDEX idx_bbk_id (bbk_id);
```

- [ ] **Step 2: 提交迁移脚本**

```bash
git add scripts/sql/tracing_user_info_migration.sql
git commit -m "feat(tracing): add database migration for user_name and bbk_id fields"
```

---

### Task 2: 中间件解析请求头

**Files:**
- Modify: `src/swe/app/middleware/tenant_identity.py:119-177`

- [ ] **Step 1: 修改 _resolve_request_identity 方法**

找到 `_resolve_request_identity` 方法（约第119-133行），修改为：

```python
def _resolve_request_identity(
    self,
    request: Request,
) -> tuple[str | None, str | None, str | None, str | None, str | None, bool]:
    """Resolve tenant, user, source, user_name, bbk_id from request headers."""
    path = request.url.path
    is_exempt = request.method == "OPTIONS" or is_tenant_exempt(path)
    tenant_id = request.headers.get("X-Tenant-Id")
    user_id = request.headers.get("X-User-Id")
    source_id = request.headers.get("X-Source-Id")
    user_name = request.headers.get("X-User-Name")
    bbk_id = request.headers.get("X-Bbk-Id")

    if not is_exempt:
        tenant_id = self._validate_tenant_id(path, tenant_id)

    return tenant_id, user_id, source_id, user_name, bbk_id, is_exempt
```

- [ ] **Step 2: 修改 _store_request_state 方法**

找到 `_store_request_state` 方法（约第160-177行），修改为：

```python
def _store_request_state(
    self,
    request: Request,
    tenant_id: str | None,
    user_id: str | None,
    source_id: str | None,
    user_name: str | None,
    bbk_id: str | None,
) -> None:
    """Store identity in request state for downstream use."""
    effective_tenant_id = resolve_runtime_tenant_id(tenant_id, source_id)
    if tenant_id:
        request.state.tenant_id = tenant_id
    if effective_tenant_id:
        request.state.effective_tenant_id = effective_tenant_id
    if user_id:
        request.state.user_id = user_id
    if source_id:
        request.state.source_id = source_id
    if user_name:
        request.state.user_name = user_name
    if bbk_id:
        request.state.bbk_id = bbk_id
```

- [ ] **Step 3: 修改 dispatch 方法调用**

找到调用 `_resolve_request_identity` 和 `_store_request_state` 的位置（dispatch 方法中），修改解包和调用：

```python
tenant_id, user_id, source_id, user_name, bbk_id, is_exempt = self._resolve_request_identity(request)
# ... 中间代码保持不变 ...
self._store_request_state(request, tenant_id, user_id, source_id, user_name, bbk_id)
```

- [ ] **Step 4: 提交中间件修改**

```bash
git add src/swe/app/middleware/tenant_identity.py
git commit -m "feat(middleware): parse X-User-Name and X-Bbk-Id headers"
```

---

### Task 3: Pydantic 模型添加字段

**Files:**
- Modify: `src/swe/tracing/models.py`

- [ ] **Step 1: Span 类添加字段**

找到 `Span` 类（第34-95行），在 `user_id` 字段后添加：

```python
user_id: str = Field(default="", description="User identifier")
user_name: Optional[str] = Field(default=None, description="User name")
bbk_id: Optional[str] = Field(default=None, description="BBK identifier")
session_id: str = Field(default="", description="Session identifier")
```

- [ ] **Step 2: Trace 类添加字段**

找到 `Trace` 类（第97-156行），在 `user_id` 字段后添加：

```python
user_id: str = Field(description="User identifier")
user_name: Optional[str] = Field(default=None, description="User name")
bbk_id: Optional[str] = Field(default=None, description="BBK identifier")
session_id: str = Field(description="Session identifier")
```

- [ ] **Step 3: UserListItem 类添加字段**

找到 `UserListItem` 类（第382-390行），修改为：

```python
class UserListItem(BaseModel):
    """User list item with stats."""

    user_id: str
    user_name: Optional[str] = Field(default=None, description="User name")
    bbk_id: Optional[str] = Field(default=None, description="BBK identifier")
    total_sessions: int = 0
    total_conversations: int = 0
    total_tokens: int = 0
    total_skills: int = 0
    last_active: Optional[datetime] = None
```

- [ ] **Step 4: TraceListItem 类添加字段**

找到 `TraceListItem` 类（第393-409行），在 `user_id` 字段后添加：

```python
user_id: str
user_name: Optional[str] = Field(default=None, description="User name")
bbk_id: Optional[str] = Field(default=None, description="BBK identifier")
session_id: str
```

- [ ] **Step 5: UserMessageItem 类添加字段**

找到 `UserMessageItem` 类（第443-457行），在 `user_id` 字段后添加：

```python
user_id: str
user_name: Optional[str] = Field(default=None, description="User name")
bbk_id: Optional[str] = Field(default=None, description="BBK identifier")
session_id: str
```

- [ ] **Step 6: 提交模型修改**

```bash
git add src/swe/tracing/models.py
git commit -m "feat(tracing): add user_name and bbk_id fields to models"
```

---

### Task 4: 存储层 SQL 修改

**Files:**
- Modify: `src/swe/tracing/store.py`

- [ ] **Step 1: 修改 create_trace 方法**

找到 `create_trace` 方法（第113-151行），修改 INSERT SQL：

```python
async def create_trace(self, trace: Trace) -> None:
    """Create a new trace."""
    if self.db is None:
        return

    query = """
        INSERT INTO swe_tracing_traces (
            trace_id, source_id, user_id, user_name, bbk_id, session_id, channel, start_time,
            end_time, duration_ms, model_name, total_input_tokens,
            total_output_tokens, total_tokens, tools_used, skills_used,
            status, error, user_message
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    params = (
        trace.trace_id,
        trace.source_id,
        trace.user_id,
        trace.user_name,
        trace.bbk_id,
        trace.session_id,
        trace.channel,
        trace.start_time,
        trace.end_time,
        trace.duration_ms,
        trace.model_name,
        trace.total_input_tokens,
        trace.total_output_tokens,
        trace.total_input_tokens + trace.total_output_tokens,
        json.dumps(trace.tools_used),
        json.dumps(trace.skills_used),
        trace.status.value
        if isinstance(trace.status, TraceStatus)
        else trace.status,
        trace.error,
        trace.user_message,
    )
    await self.db.execute(query, params)
```

- [ ] **Step 2: 修改 create_span 方法**

找到 `create_span` 方法（第225-266行），修改 INSERT SQL：

```python
async def create_span(self, span: Span) -> None:
    """Create a new span."""
    if self.db is None:
        return

    query = """
        INSERT INTO swe_tracing_spans (
            span_id, trace_id, source_id, name, event_type,
            start_time, end_time, duration_ms, user_id, user_name, bbk_id, session_id, channel,
            model_name, input_tokens, output_tokens, tool_name, skill_name, mcp_server,
            tool_input, tool_output, error
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    params = (
        span.span_id,
        span.trace_id,
        span.source_id,
        span.name,
        span.event_type.value
        if isinstance(span.event_type, EventType)
        else span.event_type,
        span.start_time,
        span.end_time,
        span.duration_ms,
        span.user_id,
        span.user_name,
        span.bbk_id,
        span.session_id,
        span.channel,
        span.model_name,
        span.input_tokens,
        span.output_tokens,
        span.tool_name,
        span.skill_name,
        span.mcp_server,
        json.dumps(span.tool_input) if span.tool_input else None,
        span.tool_output,
        span.error,
    )
    await self.db.execute(query, params)
```

- [ ] **Step 3: 修改 batch_create_spans 方法**

找到 `batch_create_spans` 方法（第320-368行），修改 INSERT SQL：

```python
async def batch_create_spans(self, spans: list[Span]) -> None:
    """Batch create spans."""
    if not spans:
        return

    if self.db is None:
        return

    query = """
        INSERT INTO swe_tracing_spans (
            span_id, trace_id, source_id, name, event_type,
            start_time, end_time, duration_ms, user_id, user_name, bbk_id, session_id, channel,
            model_name, input_tokens, output_tokens, tool_name, skill_name, mcp_server,
            tool_input, tool_output, error
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    params_list = []
    for span in spans:
        params_list.append(
            (
                span.span_id,
                span.trace_id,
                span.source_id,
                span.name,
                span.event_type.value
                if isinstance(span.event_type, EventType)
                else span.event_type,
                span.start_time,
                span.end_time,
                span.duration_ms,
                span.user_id,
                span.user_name,
                span.bbk_id,
                span.session_id,
                span.channel,
                span.model_name,
                span.input_tokens,
                span.output_tokens,
                span.tool_name,
                span.skill_name,
                span.mcp_server,
                json.dumps(span.tool_input) if span.tool_input else None,
                span.tool_output,
                span.error,
            ),
        )
    await self.db.execute_many(query, params_list)
```

- [ ] **Step 4: 修改 _row_to_trace 方法**

找到 `_row_to_trace` 方法（第2411-2436行），修改为：

```python
def _row_to_trace(self, row: dict) -> Trace:
    """Convert database row to Trace model."""
    return Trace(
        trace_id=row["trace_id"],
        source_id=row["source_id"],
        user_id=row["user_id"],
        user_name=row.get("user_name"),
        bbk_id=row.get("bbk_id"),
        session_id=row["session_id"],
        channel=row["channel"],
        start_time=row["start_time"],
        end_time=row["end_time"],
        duration_ms=row["duration_ms"],
        model_name=row["model_name"],
        total_input_tokens=row["total_input_tokens"] or 0,
        total_output_tokens=row["total_output_tokens"] or 0,
        tools_used=json.loads(row["tools_used"])
        if row["tools_used"]
        else [],
        skills_used=json.loads(row["skills_used"])
        if row["skills_used"]
        else [],
        status=TraceStatus(row["status"])
        if row["status"]
        else TraceStatus.RUNNING,
        error=row["error"],
        user_message=row.get("user_message"),
    )
```

- [ ] **Step 5: 修改 _row_to_span 方法**

找到 `_row_to_span` 方法（第2438-2463行），修改为：

```python
def _row_to_span(self, row: dict) -> Span:
    """Convert database row to Span model."""
    return Span(
        span_id=row["span_id"],
        trace_id=row["trace_id"],
        source_id=row["source_id"],
        name=row["name"],
        event_type=EventType(row["event_type"]),
        start_time=row["start_time"],
        end_time=row["end_time"],
        duration_ms=row["duration_ms"],
        user_id=row.get("user_id") or "",
        user_name=row.get("user_name"),
        bbk_id=row.get("bbk_id"),
        session_id=row.get("session_id") or "",
        channel=row.get("channel") or "",
        model_name=row["model_name"],
        input_tokens=row["input_tokens"],
        output_tokens=row["output_tokens"],
        tool_name=row["tool_name"],
        skill_name=row["skill_name"],
        mcp_server=row.get("mcp_server"),
        tool_input=json.loads(row["tool_input"])
        if row["tool_input"]
        else None,
        tool_output=row["tool_output"],
        error=row["error"],
    )
```

- [ ] **Step 6: 提交存储层修改**

```bash
git add src/swe/tracing/store.py
git commit -m "feat(tracing): update store SQL for user_name and bbk_id fields"
```

---

### Task 5: 管理层修改

**Files:**
- Modify: `src/swe/tracing/manager.py`

- [ ] **Step 1: 修改 TraceContext 类**

找到 `TraceContext` 类（第28-95行），修改 `__init__` 方法：

```python
def __init__(
    self,
    trace_id: str,
    user_id: str,
    session_id: str,
    channel: str,
    source_id: str,
    user_name: Optional[str] = None,
    bbk_id: Optional[str] = None,
):
    self.trace_id = trace_id
    self.user_id = user_id
    self.user_name = user_name
    self.bbk_id = bbk_id
    self.session_id = session_id
    self.channel = channel
    self.source_id = source_id
    self.start_time = datetime.now()
    self.trace: Optional[Trace] = None
    self._span_stack: list[str] = []
    self._active_skills: list[str] = []
    self.skill_detector: Optional[Any] = None
    self.enabled_skills: list[str] = []
```

- [ ] **Step 2: 修改 start_trace 方法**

找到 `start_trace` 方法（约第246-299行），添加 `user_name` 和 `bbk_id` 参数：

```python
async def start_trace(
    self,
    user_id: str,
    session_id: str,
    channel: str,
    source_id: str,
    user_message: Optional[str] = None,
    user_name: Optional[str] = None,
    bbk_id: Optional[str] = None,
) -> str:
    """Start a new trace.

    Args:
        user_id: User identifier
        session_id: Session identifier
        channel: Channel identifier
        source_id: Source identifier for data isolation
        user_message: Optional user input message
        user_name: Optional user name
        bbk_id: Optional BBK identifier

    Returns:
        Trace ID
    """
    if not self.enabled:
        return ""

    trace_id = str(uuid.uuid4())
    now = datetime.now()

    trace = Trace(
        trace_id=trace_id,
        source_id=source_id,
        user_id=user_id,
        user_name=user_name,
        bbk_id=bbk_id,
        session_id=session_id,
        channel=channel,
        start_time=now,
        status=TraceStatus.RUNNING,
        user_message=user_message,
    )

    # Create context
    ctx = TraceContext(
        trace_id=trace_id,
        user_id=user_id,
        session_id=session_id,
        channel=channel,
        source_id=source_id,
        user_name=user_name,
        bbk_id=bbk_id,
    )
    ctx.trace = trace

    # Store trace
    await self.store.create_trace(trace)

    # Set context
    set_current_trace(ctx)
    self._active_traces[trace_id] = trace

    return trace_id
```

- [ ] **Step 3: 修改 emit_span 方法**

找到 `emit_span` 方法（约第431-511行），添加 `user_name` 和 `bbk_id` 参数：

```python
async def emit_span(
    self,
    trace_id: str,
    name: str,
    event_type: EventType,
    source_id: str,
    user_id: str = "",
    user_name: Optional[str] = None,
    bbk_id: Optional[str] = None,
    session_id: str = "",
    channel: str = "",
    model_name: Optional[str] = None,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    tool_name: Optional[str] = None,
    skill_name: Optional[str] = None,
    mcp_server: Optional[str] = None,
    tool_input: Optional[dict[str, Any]] = None,
    tool_output: Optional[str] = None,
    error: Optional[str] = None,
) -> str:
    # ... 方法实现保持不变，只需在创建 Span 时传入新字段
    span = Span(
        span_id=span_id,
        trace_id=trace_id,
        source_id=source_id,
        name=name,
        event_type=event_type,
        start_time=datetime.now(),
        user_id=user_id,
        user_name=user_name,
        bbk_id=bbk_id,
        session_id=session_id,
        channel=channel,
        model_name=model_name,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        tool_name=tool_name,
        skill_name=skill_name,
        mcp_server=mcp_server,
        tool_input=tool_input,
        tool_output=tool_output,
        error=error,
    )
    # ...
```

- [ ] **Step 4: 修改 emit_llm_input 方法**

找到 `emit_llm_input` 方法，添加 `user_name` 和 `bbk_id` 参数：

```python
async def emit_llm_input(
    self,
    trace_id: str,
    model_name: str,
    input_tokens: int,
    user_id: str = "",
    user_name: Optional[str] = None,
    bbk_id: Optional[str] = None,
    session_id: str = "",
    channel: str = "",
    source_id: str = "",
) -> Optional[str]:
    """Emit LLM input event."""
    # ... 调用 emit_span 时传入新参数
    return await self.emit_span(
        trace_id=trace_id,
        name=f"llm_input.{model_name}",
        event_type=EventType.LLM_INPUT,
        source_id=source_id,
        user_id=user_id,
        user_name=user_name,
        bbk_id=bbk_id,
        session_id=session_id,
        channel=channel,
        model_name=model_name,
        input_tokens=input_tokens,
    )
```

- [ ] **Step 5: 修改 emit_tool_call_start 方法**

找到 `emit_tool_call_start` 方法，添加 `user_name` 和 `bbk_id` 参数：

```python
async def emit_tool_call_start(
    self,
    trace_id: str,
    tool_name: str,
    tool_input: Optional[dict[str, Any]],
    source_id: str,
    user_id: str = "",
    user_name: Optional[str] = None,
    bbk_id: Optional[str] = None,
    session_id: str = "",
    channel: str = "",
    mcp_server: Optional[str] = None,
) -> str:
    # ... 调用 emit_span 时传入新参数
```

- [ ] **Step 6: 修改 emit_skill_invocation 方法**

找到 `emit_skill_invocation` 方法，添加 `user_name` 和 `bbk_id` 参数：

```python
async def emit_skill_invocation(
    self,
    trace_id: str,
    skill_name: str,
    source_id: str,
    user_id: str = "",
    user_name: Optional[str] = None,
    bbk_id: Optional[str] = None,
    session_id: str = "",
    channel: str = "",
    skill_input: Optional[dict[str, Any]] = None,
) -> Optional[str]:
    # ... 调用 emit_span 时传入新参数
```

- [ ] **Step 7: 提交管理层修改**

```bash
git add src/swe/tracing/manager.py
git commit -m "feat(tracing): add user_name and bbk_id to TraceContext and start_trace"
```

---

### Task 6: TracingHook 修改

**Files:**
- Modify: `src/swe/agents/hooks/tracing.py`

- [ ] **Step 1: 修改 __init__ 方法**

找到 `TracingHook.__init__` 方法（第25-52行），修改为：

```python
def __init__(
    self,
    trace_id: str,
    user_id: str,
    session_id: str,
    channel: str,
    source_id: str,
    user_name: Optional[str] = None,
    bbk_id: Optional[str] = None,
):
    """Initialize tracing hook."""
    self.trace_id = trace_id
    self.user_id = user_id
    self.user_name = user_name
    self.bbk_id = bbk_id
    self.session_id = session_id
    self.channel = channel
    self.source_id = source_id
    self._current_llm_span_id: Optional[str] = None
    self._current_tool_span_id: Optional[str] = None
    self._tool_spans: dict[str, str] = {}
    self._in_skill_context: bool = False
```

- [ ] **Step 2: 修改 on_llm_start 方法**

```python
async def on_llm_start(
    self,
    model_name: str,
    input_tokens: int = 0,
) -> Optional[str]:
    # ... 调用 manager.emit_llm_input 时传入新参数
    span_id = await manager.emit_llm_input(
        trace_id=self.trace_id,
        model_name=model_name,
        input_tokens=input_tokens,
        user_id=self.user_id,
        user_name=self.user_name,
        bbk_id=self.bbk_id,
        session_id=self.session_id,
        channel=self.channel,
        source_id=self.source_id,
    )
    # ...
```

- [ ] **Step 3: 修改 on_tool_start 方法**

```python
async def on_tool_start(
    self,
    tool_name: str,
    tool_input: Optional[dict[str, Any]],
    tool_call_id: Optional[str] = None,
    mcp_server: Optional[str] = None,
) -> str:
    # ... 调用 manager.emit_tool_call_start 时传入新参数
    span_id = await manager.emit_tool_call_start(
        trace_id=self.trace_id,
        tool_name=tool_name,
        tool_input=tool_input,
        source_id=self.source_id,
        user_id=self.user_id,
        user_name=self.user_name,
        bbk_id=self.bbk_id,
        session_id=self.session_id,
        channel=self.channel,
        mcp_server=mcp_server,
    )
    # ...
```

- [ ] **Step 4: 修改 on_skill_start 方法**

```python
async def on_skill_start(
    self,
    skill_name: str,
    skill_input: Optional[dict[str, Any]] = None,
) -> Optional[str]:
    # ... 调用 manager.emit_skill_invocation 时传入新参数
    span_id = await manager.emit_skill_invocation(
        trace_id=self.trace_id,
        skill_name=skill_name,
        source_id=self.source_id,
        user_id=self.user_id,
        user_name=self.user_name,
        bbk_id=self.bbk_id,
        session_id=self.session_id,
        channel=self.channel,
        skill_input=skill_input,
    )
    # ...
```

- [ ] **Step 5: 提交钩子修改**

```bash
git add src/swe/agents/hooks/tracing.py
git commit -m "feat(tracing): pass user_name and bbk_id in TracingHook"
```

---

### Task 7: Runner 层修改

**Files:**
- Modify: `src/swe/app/runner/runner.py`

- [ ] **Step 1: 找到 query_handler 方法中启动 trace 的位置**

在 `query_handler` 方法（约第534-564行）中，找到提取用户信息和调用 `start_trace` 的位置，修改为：

```python
# 提取用户信息
session_id_for_trace = getattr(request, "session_id", "") or ""
user_id_for_trace = getattr(request, "user_id", "") or ""
user_name_for_trace = getattr(request, "user_name", None)
bbk_id_for_trace = getattr(request, "bbk_id", None)
channel_for_trace = getattr(request, "channel", DEFAULT_CHANNEL)
source_id_for_trace = getattr(request, "source_id", None) or get_default_source_id()

# 如果 request 上没有，尝试从 request.state 获取（中间件设置）
if user_name_for_trace is None and hasattr(request, "state"):
    user_name_for_trace = getattr(request.state, "user_name", None)
if bbk_id_for_trace is None and hasattr(request, "state"):
    bbk_id_for_trace = getattr(request.state, "bbk_id", None)

# 启动 trace
trace_id = await trace_mgr.start_trace(
    user_id=user_id_for_trace,
    session_id=session_id_for_trace,
    channel=channel_for_trace,
    source_id=source_id_for_trace,
    user_message=user_message,
    user_name=user_name_for_trace,
    bbk_id=bbk_id_for_trace,
)
```

- [ ] **Step 2: 修改 TracingHook 创建位置**

找到创建 `TracingHook` 的位置，添加新参数：

```python
tracing_hook = TracingHook(
    trace_id=trace_id,
    user_id=user_id_for_trace,
    session_id=session_id_for_trace,
    channel=channel_for_trace,
    source_id=source_id_for_trace,
    user_name=user_name_for_trace,
    bbk_id=bbk_id_for_trace,
)
```

- [ ] **Step 3: 提交 Runner 修改**

```bash
git add src/swe/app/runner/runner.py
git commit -m "feat(runner): pass user_name and bbk_id to trace manager"
```

---

### Task 8: 前端 API 类型修改

**Files:**
- Modify: `console/src/api/modules/tracing.ts`

- [ ] **Step 1: 修改 UserListItem 接口**

找到 `UserListItem` 接口（约第82-88行），修改为：

```typescript
export interface UserListItem {
  user_id: string;
  user_name?: string;
  bbk_id?: string;
  total_sessions: number;
  total_conversations: number;
  total_tokens: number;
  total_skills: number;
  last_active?: string;
}
```

- [ ] **Step 2: 修改 TraceListItem 接口**

找到 `TraceListItem` 接口（约第90-103行），添加新字段：

```typescript
export interface TraceListItem {
  trace_id: string;
  source_id: string;
  user_id: string;
  user_name?: string;
  bbk_id?: string;
  session_id: string;
  channel: string;
  start_time: string;
  duration_ms?: number;
  total_tokens: number;
  total_input_tokens: number;
  total_output_tokens: number;
  model_name?: string;
  status: string;
  skills_count: number;
}
```

- [ ] **Step 3: 修改 Trace 接口**

找到 `Trace` 接口（约第142-158行），添加新字段：

```typescript
export interface Trace {
  trace_id: string;
  source_id: string;
  user_id: string;
  user_name?: string;
  bbk_id?: string;
  session_id: string;
  channel: string;
  start_time: string;
  end_time?: string;
  duration_ms?: number;
  model_name?: string;
  total_input_tokens: number;
  total_output_tokens: number;
  tools_used: string[];
  skills_used: string[];
  status: string;
  error?: string;
  user_message?: string;
}
```

- [ ] **Step 4: 修改 Span 接口**

找到 `Span` 接口（约第160-176行），添加新字段：

```typescript
export interface Span {
  span_id: string;
  trace_id: string;
  source_id: string;
  name: string;
  event_type: string;
  start_time: string;
  end_time?: string;
  duration_ms?: number;
  user_id: string;
  user_name?: string;
  bbk_id?: string;
  session_id: string;
  channel: string;
  model_name?: string;
  input_tokens?: number;
  output_tokens?: number;
  tool_name?: string;
  skill_name?: string;
  mcp_server?: string;
  tool_input?: Record<string, unknown>;
  tool_output?: string;
  error?: string;
}
```

- [ ] **Step 5: 修改 UserMessageItem 接口**

找到 `UserMessageItem` 接口（约第242-253行），添加新字段：

```typescript
export interface UserMessageItem {
  trace_id: string;
  source_id: string;
  user_id: string;
  user_name?: string;
  bbk_id?: string;
  session_id: string;
  channel: string;
  user_message?: string;
  input_tokens: number;
  output_tokens: number;
  model_name?: string;
  start_time: string;
  duration_ms?: number;
}
```

- [ ] **Step 6: 提交前端 API 类型修改**

```bash
git add console/src/api/modules/tracing.ts
git commit -m "feat(console): add user_name and bbk_id to tracing API types"
```

---

### Task 9: 前端展示修改

**Files:**
- Modify: `console/src/pages/Analytics/BusinessOverview/index.tsx`

- [ ] **Step 1: 修改 UserRow 类型定义**

找到 `UserRow` 类型定义（约第23-30行），修改为：

```typescript
interface UserRow {
  key: string;
  user_id: string;
  user_name?: string;
  bbk_id?: string;
  total_sessions: number;
  total_conversations: number;
  total_tokens: number;
  total_skills: number;
  last_active: string;
}
```

- [ ] **Step 2: 修改用户列表数据转换**

找到用户列表数据处理位置，添加新字段映射：

```typescript
const userRows: UserRow[] = users.map((user) => ({
  key: user.user_id,
  user_id: user.user_id,
  user_name: user.user_name,
  bbk_id: user.bbk_id,
  total_sessions: user.total_sessions,
  total_conversations: user.total_conversations,
  total_tokens: user.total_tokens,
  total_skills: user.total_skills,
  last_active: user.last_active
    ? new Date(user.last_active).toLocaleString("zh-CN")
    : "-",
}));
```

- [ ] **Step 3: 修改用户列表表格列定义**

找到用户列表的 columns 定义，修改用户列的 render 函数：

```typescript
{
  title: "用户",
  dataIndex: "user_id",
  key: "user_id",
  render: (_: unknown, record: UserRow) => (
    <span>
      {record.user_name || record.user_id}
      {record.bbk_id && (
        <span style={{ color: "#999", marginLeft: 8 }}>
          ({record.bbk_id})
        </span>
      )}
    </span>
  ),
},
```

- [ ] **Step 4: 提交前端展示修改**

```bash
git add console/src/pages/Analytics/BusinessOverview/index.tsx
git commit -m "feat(console): display user_name and bbk_id in BusinessOverview"
```

---

### Task 10: 验证测试

- [ ] **Step 1: 执行数据库迁移**

```bash
mysql -u <user> -p < scripts/sql/tracing_user_info_migration.sql
```

- [ ] **Step 2: 验证后端服务启动**

```bash
# 启动服务，确认无报错
swe app
```

- [ ] **Step 3: 发送带新请求头的请求**

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "X-Tenant-Id: test" \
  -H "X-User-Id: user001" \
  -H "X-User-Name: 测试用户" \
  -H "X-Bbk-Id: BBK001" \
  -H "X-Source-Id: test-source" \
  -H "Content-Type: application/json" \
  -d '{"message": "hello"}'
```

- [ ] **Step 4: 验证数据库记录**

```sql
SELECT trace_id, user_id, user_name, bbk_id FROM swe_tracing_traces
WHERE user_id = 'user001' ORDER BY start_time DESC LIMIT 1;
```

- [ ] **Step 5: 验证前端展示**

打开业务概览页面，确认用户列表正确显示用户姓名。

---

### Task 11: 最终提交

- [ ] **Step 1: 确认所有修改已提交**

```bash
git status
```

- [ ] **Step 2: 推送到远程仓库**

```bash
git push origin feature_market
```
