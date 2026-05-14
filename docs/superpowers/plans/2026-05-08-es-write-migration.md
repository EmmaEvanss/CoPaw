# ES 写入迁移实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 SWE 服务的 ES 写入操作迁移到 Monitor 服务，SWE 通过 HTTP API 调用 Monitor 写入 model_output。

**Architecture:** Monitor 新增 ES 写入 API，SWE runner.py 改为 HTTP 调用，清理 SWE 的 ES 模块代码。

**Tech Stack:** FastAPI, httpx, elasticsearch[async] 7.x（兼容 ES 6.x 服务端）

---

## ES 版本兼容性说明

- **服务端版本**: ES 6.6.1
- **客户端版本**: elasticsearch 7.x（向下兼容 ES 6.x）
- **兼容方式**: 使用 `doc_type="_doc"` 参数，ES 6.x 必需，ES 7.x 可选

---

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| `monitor/pyproject.toml` | 修改 | 添加 ES 依赖 |
| `monitor/src/monitor/config/constant.py` | 修改 | 修正 ES_INDEX 默认值 |
| `monitor/src/monitor/app/database/elasticsearch.py` | 修改 | 新增 index_message() 方法，ES 6.x 兼容 |
| `monitor/src/monitor/app/routers/tracing.py` | 修改 | 新增 POST /model-output API |
| `monitor/src/monitor/app/models/tracing.py` | 修改 | 新增 ModelOutputRequest 模型 |
| `src/swe/app/runner/runner.py` | 修改 | 改为 HTTP 调用 Monitor API |
| `src/swe/app/_app.py` | 修改 | 移除 ES 初始化代码 |
| `src/swe/elasticsearch/` | 删除 | 删除整个目录 |
| `src/swe/config/envs/prd.json` | 修改 | 移除 SWE_ES_* 配置 |
| `src/swe/config/envs/dev.json` | 修改 | 移除 SWE_ES_* 配置 |
| `tests/unit/elasticsearch/` | 删除 | 删除测试目录 |

---

### Task 1: 添加 Monitor ES 依赖

**Files:**
- Modify: `monitor/pyproject.toml`

- [ ] **Step 1: 添加 elasticsearch 依赖**

```toml
dependencies = [
    "fastapi>=0.100.0",
    "uvicorn>=0.23.0",
    "click>=8.0.0",
    "pyyaml>=6.0",
    "aiomysql>=0.2.0",
    "openpyxl>=3.1.0",
    "httpx>=0.27.0",
    "pydantic>=2.0.0",
    "elasticsearch[async]>=7.0.0,<8.0.0",
]
```

- [ ] **Step 2: 验证语法**

Run: `cd "D:\Vibe Coding\CoPaw1.0.0\CoPaw\monitor" && python -c "import tomllib; tomllib.load(open('pyproject.toml', 'rb'))"`
Expected: 无输出（语法正确）

- [ ] **Step 3: 提交**

```bash
git add monitor/pyproject.toml
git commit -m "feat(monitor): add elasticsearch dependency for ES 6.x/7.x"
```

---

### Task 2: 修正 Monitor ES_INDEX 默认值

**Files:**
- Modify: `monitor/src/monitor/config/constant.py:200`

- [ ] **Step 1: 修改 ES_INDEX 默认值**

```python
# 修改前
ES_INDEX = EnvVarLoader.get_str("ES_INDEX", "swe_messages")

# 修改后
ES_INDEX = EnvVarLoader.get_str("ES_INDEX", "swe_model_outputs")
```

- [ ] **Step 2: 验证语法**

Run: `cd "D:\Vibe Coding\CoPaw1.0.0\CoPaw" && python -m py_compile monitor/src/monitor/config/constant.py`
Expected: 无输出（语法正确）

- [ ] **Step 3: 提交**

```bash
git add monitor/src/monitor/config/constant.py
git commit -m "fix(monitor): correct ES_INDEX default to swe_model_outputs"
```

---

### Task 2: Monitor ES Client 新增 index_message 方法

**Files:**
- Modify: `monitor/src/monitor/app/database/elasticsearch.py`

- [ ] **Step 1: 新增 index_message 方法**

在 `ESClient` 类中新增方法（在 `get_message` 方法后）：

```python
async def index_message(self, trace_id: str, model_output: str) -> bool:
    """写入 model_output 到 ES.

    Args:
        trace_id: 追踪 ID
        model_output: 模型输出文本

    Returns:
        是否写入成功
    """
    if not self._connected or not self._es:
        logger.warning("ES index skipped: connected=%s", self._connected)
        return False

    from datetime import datetime

    doc = {
        "trace_id": trace_id,
        "model_output": model_output,
        "created_at": datetime.utcnow().isoformat(),
    }
    try:
        result = await self._es.index(
            index=self._index,
            id=trace_id,
            body=doc,
            refresh=True,
        )
        logger.info(
            "ES index success: trace_id=%s, result=%s",
            trace_id,
            result.get("result") if result else "unknown",
        )
        return True
    except Exception as e:
        logger.warning(
            "Failed to index model_output for trace_id=%s: %s",
            trace_id,
            e,
        )
        return False
```

- [ ] **Step 2: 验证语法**

Run: `cd "D:\Vibe Coding\CoPaw1.0.0\CoPaw" && python -m py_compile monitor/src/monitor/app/database/elasticsearch.py`
Expected: 无输出（语法正确）

- [ ] **Step 3: 提交**

```bash
git add monitor/src/monitor/app/database/elasticsearch.py
git commit -m "feat(monitor): add index_message method to ESClient"
```

---

### Task 3: Monitor 新增数据模型

**Files:**
- Modify: `monitor/src/monitor/app/models/tracing.py`

- [ ] **Step 1: 新增 ModelOutputRequest 模型**

在文件末尾添加：

```python
class ModelOutputRequest(BaseModel):
    """Model output 写入请求."""

    trace_id: str = Field(description="追踪 ID")
    model_output: str = Field(description="模型输出文本")
```

- [ ] **Step 2: 验证语法**

Run: `cd "D:\Vibe Coding\CoPaw1.0.0\CoPaw" && python -m py_compile monitor/src/monitor/app/models/tracing.py`
Expected: 无输出（语法正确）

- [ ] **Step 3: 提交**

```bash
git add monitor/src/monitor/app/models/tracing.py
git commit -m "feat(monitor): add ModelOutputRequest model"
```

---

### Task 4: Monitor 新增 POST /model-output API

**Files:**
- Modify: `monitor/src/monitor/app/routers/tracing.py`

- [ ] **Step 1: 导入新模型和 ES 客户端**

在文件顶部的导入部分添加：

```python
from ..models.tracing import (
    # ... 现有导入 ...
    ModelOutputRequest,
)
from ..database import get_es_client
```

- [ ] **Step 2: 新增 API 端点**

在路由定义后添加：

```python
# ===== Model Output 写入 =====


@router.post("/model-output")
async def index_model_output(
    request: Request,
    body: ModelOutputRequest,
):
    """写入 model_output 到 ES.

    Args:
        body: 包含 trace_id 和 model_output

    Returns:
        写入结果
    """
    es_client = get_es_client()
    if es_client is None or not es_client.is_connected:
        # ES 未配置，静默跳过（与原 SWE 行为一致）
        logger.info("ES not configured, skipping model_output write")
        return {"status": "skipped", "reason": "ES not configured"}

    try:
        success = await es_client.index_message(
            body.trace_id,
            body.model_output,
        )
        if success:
            return {"status": "success"}
        else:
            return {"status": "failed"}
    except Exception as e:
        logger.warning("Failed to write model_output: %s", e)
        return {"status": "failed", "error": str(e)}
```

- [ ] **Step 3: 验证语法**

Run: `cd "D:\Vibe Coding\CoPaw1.0.0\CoPaw" && python -m py_compile monitor/src/monitor/app/routers/tracing.py`
Expected: 无输出（语法正确）

- [ ] **Step 4: 提交**

```bash
git add monitor/src/monitor/app/routers/tracing.py
git commit -m "feat(monitor): add POST /model-output API for ES write"
```

---

### Task 5: SWE runner.py 改为调用 Monitor API

**Files:**
- Modify: `src/swe/app/runner/runner.py`

- [ ] **Step 1: 添加 HTTP 客户端函数**

在文件顶部导入部分后添加：

```python
import httpx
```

在 `_extract_assistant_response` 函数附近添加新函数：

```python
async def _index_model_output_to_monitor(
    trace_id: str,
    model_output: str,
) -> None:
    """通过 Monitor API 写入 model_output 到 ES.

    Args:
        trace_id: 追踪 ID
        model_output: 模型输出文本
    """
    import os

    monitor_url = os.environ.get(
        "SWE_MONITOR_API_URL",
        "http://127.0.0.1:9090",
    )
    url = f"{monitor_url}/api/monitor/tracing/model-output"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                url,
                json={
                    "trace_id": trace_id,
                    "model_output": model_output,
                },
            )
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "success":
                    logger.info(
                        "Model output indexed via Monitor API: trace_id=%s",
                        trace_id,
                    )
                else:
                    logger.info(
                        "Model output write skipped: trace_id=%s, reason=%s",
                        trace_id,
                        result.get("reason", "unknown"),
                    )
            else:
                logger.warning(
                    "Monitor API returned %s: trace_id=%s",
                    response.status_code,
                    trace_id,
                )
    except httpx.TimeoutException:
        logger.warning("Monitor API timeout: trace_id=%s", trace_id)
    except Exception as e:
        logger.warning(
            "Failed to call Monitor API for model_output: %s",
            e,
        )
```

- [ ] **Step 2: 替换 ES 直连写入代码**

将 `runner.py` 第 830-859 行的 ES 直连写入代码：

```python
# 原代码（删除）
# Index model output to Elasticsearch
if trace_id and agent is not None:
    assistant_response = _extract_assistant_response(agent)
    logger.info(
        "ES write check: trace_id=%s, response_len=%d",
        trace_id,
        len(assistant_response) if assistant_response else 0,
    )
    if assistant_response:
        try:
            from ...elasticsearch import get_es_client

            es_client = get_es_client()
            if es_client and es_client.is_connected:
                await es_client.index_message(
                    trace_id,
                    assistant_response,
                )
            else:
                logger.warning(
                    "ES client not available: connected=%s",
                    es_client.is_connected if es_client else None,
                )
        except Exception as es_err:
            logger.warning(
                "Failed to index model output to ES: %s",
                es_err,
            )
    else:
        logger.info("ES write skipped: empty assistant_response")
```

替换为：

```python
# 通过 Monitor API 写入 model_output 到 ES
if trace_id and agent is not None:
    assistant_response = _extract_assistant_response(agent)
    if assistant_response:
        await _index_model_output_to_monitor(trace_id, assistant_response)
```

- [ ] **Step 3: 验证语法**

Run: `cd "D:\Vibe Coding\CoPaw1.0.0\CoPaw" && python -m py_compile src/swe/app/runner/runner.py`
Expected: 无输出（语法正确）

- [ ] **Step 4: 提交**

```bash
git add src/swe/app/runner/runner.py
git commit -m "refactor(swe): use Monitor API for ES model_output write"
```

---

### Task 6: 清理 SWE ES 初始化代码

**Files:**
- Modify: `src/swe/app/_app.py`

- [ ] **Step 1: 移除 ES 初始化代码（第 319-342 行）**

删除以下代码：

```python
# --- Initialize Elasticsearch client for model output storage ---
es_client = None
try:
    from ..elasticsearch import get_elasticsearch_config, init_es_client

    es_config = get_elasticsearch_config()
    if es_config.host:
        es_client = init_es_client(es_config)
        if es_client:
            await es_client.connect()
            if es_client.is_connected:
                logger.info("Elasticsearch client connected")
            else:
                logger.warning("Elasticsearch client failed to connect")
    else:
        logger.info("Elasticsearch is disabled (no host configured)")
except Exception as e:
    import traceback

    logger.warning(
        "Failed to initialize Elasticsearch client: %s\n%s",
        e,
        traceback.format_exc(),
    )
```

- [ ] **Step 2: 移除 ES 关闭代码（第 399-405 行）**

删除以下代码：

```python
# Close Elasticsearch client
if es_client:
    try:
        await es_client.close()
        logger.info("Elasticsearch client closed")
    except Exception as e:
        logger.warning("Error closing Elasticsearch client: %s", e)
```

- [ ] **Step 3: 验证语法**

Run: `cd "D:\Vibe Coding\CoPaw1.0.0\CoPaw" && python -m py_compile src/swe/app/_app.py`
Expected: 无输出（语法正确）

- [ ] **Step 4: 提交**

```bash
git add src/swe/app/_app.py
git commit -m "refactor(swe): remove direct ES client initialization"
```

---

### Task 7: 删除 SWE ES 模块目录

**Files:**
- Delete: `src/swe/elasticsearch/client.py`
- Delete: `src/swe/elasticsearch/config.py`
- Delete: `src/swe/elasticsearch/__init__.py`
- Delete: `src/swe/elasticsearch/` 目录

- [ ] **Step 1: 删除整个 elasticsearch 目录**

```bash
rm -rf src/swe/elasticsearch/
```

- [ ] **Step 2: 验证删除成功**

Run: `ls src/swe/elasticsearch/ 2>&1`
Expected: `No such file or directory`

- [ ] **Step 3: 提交**

```bash
git add -A
git commit -m "refactor(swe): remove elasticsearch module (migrated to Monitor)"
```

---

### Task 8: 清理 SWE 配置文件

**Files:**
- Modify: `src/swe/config/envs/prd.json`
- Modify: `src/swe/config/envs/dev.json`

- [ ] **Step 1: 从 prd.json 移除 SWE_ES_* 配置**

删除以下行：

```json
"SWE_ES_HOST": "",
"SWE_ES_PORT": "9200",
"SWE_ES_USER": "",
"SWE_ES_ACCESS": "",
"SWE_ES_INDEX": "swe_model_outputs",
```

- [ ] **Step 2: 从 dev.json 移除 SWE_ES_* 配置**

删除同样的配置行。

- [ ] **Step 3: 验证 JSON 格式**

Run: `cd "D:\Vibe Coding\CoPaw1.0.0\CoPaw" && python -c "import json; json.load(open('src/swe/config/envs/prd.json')); json.load(open('src/swe/config/envs/dev.json')); print('JSON OK')"`
Expected: `JSON OK`

- [ ] **Step 4: 提交**

```bash
git add src/swe/config/envs/prd.json src/swe/config/envs/dev.json
git commit -m "refactor(swe): remove SWE_ES_* config (migrated to Monitor)"
```

---

### Task 9: 删除 SWE ES 测试目录

**Files:**
- Delete: `tests/unit/elasticsearch/`

- [ ] **Step 1: 删除测试目录**

```bash
rm -rf tests/unit/elasticsearch/
```

- [ ] **Step 2: 验证删除成功**

Run: `ls tests/unit/elasticsearch/ 2>&1`
Expected: `No such file or directory`

- [ ] **Step 3: 提交**

```bash
git add -A
git commit -m "test(swe): remove elasticsearch unit tests (migrated to Monitor)"
```

---

### Task 10: 验证整体功能

**Files:**
- 无文件修改，仅验证

- [ ] **Step 1: 验证 Monitor 服务语法**

Run: `cd "D:\Vibe Coding\CoPaw1.0.0\CoPaw" && python -m py_compile monitor/src/monitor/app/routers/tracing.py monitor/src/monitor/app/database/elasticsearch.py monitor/src/monitor/app/models/tracing.py`
Expected: 无输出（语法正确）

- [ ] **Step 2: 验证 SWE 服务语法**

Run: `cd "D:\Vibe Coding\CoPaw1.0.0\CoPaw" && python -m py_compile src/swe/app/_app.py src/swe/app/runner/runner.py`
Expected: 无输出（语法正确）

- [ ] **Step 3: 最终提交（如有遗漏）**

```bash
git status
# 如有未提交文件，提交它们
git add -A
git commit -m "chore: cleanup after ES write migration"
```

---

## 自检清单

- [x] Spec coverage: 所有设计文档要求都有对应任务
- [x] Placeholder scan: 无 TBD/TODO 占位符
- [x] Type consistency: ModelOutputRequest 与 API 参数一致
- [x] ES_INDEX 默认值已修正为 `swe_model_outputs`
- [x] 错误处理：ES 未配置时静默跳过，不阻塞主流程
