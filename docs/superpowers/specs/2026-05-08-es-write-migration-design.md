# ES 写入迁移设计：SWE → Monitor

## 背景

当前 SWE 服务直接连接 Elasticsearch 写入 model_output。为统一 ES 访问，将写入操作迁移到 Monitor 服务，SWE 通过 HTTP API 调用。

## 目标

- SWE 服务不再直连 ES，通过 HTTP API 调用 Monitor 写入 model_output
- Monitor 服务提供 ES 写入 API
- 清理 SWE 服务中的 ES 相关代码

## 架构变更

```
【变更前】
┌───────────┐
│  SWE 服务  │───ES写入──▶ Elasticsearch
└───────────┘
      │
      ▼
   MySQL

【变更后】
┌───────────┐                       ┌───────────┐
│  SWE 服务  │───HTTP POST──▶ Monitor │───ES写入──▶ Elasticsearch
└───────────┘                       └───────────┘
      │                                   │
      ▼                                   ▼
   MySQL                              MySQL
```

## API 设计

### Monitor 新增 API

```
POST /api/monitor/tracing/model-output
```

**请求体：**
```json
{
  "trace_id": "string",
  "model_output": "string"
}
```

**响应：**
- 200: 写入成功
- 503: ES 未配置

### 错误处理

| 场景 | HTTP 状态码 | 处理方式 |
|------|-------------|----------|
| ES 未配置 | 200 | 静默跳过（与原行为一致） |
| ES 写入失败 | 200 | 记录日志，不影响主流程 |

**注意**：写入失败不应阻塞 SWE 主流程，因此使用 200 状态码 + 日志警告。

## 配置修正

Monitor 服务的 ES_INDEX 默认值需修正：

| 配置 | 修正前 | 修正后 |
|------|--------|--------|
| ES_INDEX | `swe_messages` | `swe_model_outputs` |

## Monitor 代码变更

### 1. ES Client 新增写入方法

文件：`monitor/src/monitor/app/database/elasticsearch.py`

新增 `index_message()` 方法，复用 SWE 现有实现。

### 2. 新增 API 路由

文件：`monitor/src/monitor/app/routers/tracing.py`

新增 `POST /model-output` 端点。

## SWE 代码变更

### 1. runner.py 修改

文件：`src/swe/app/runner/runner.py`

将 ES 直连写入改为 HTTP 调用 Monitor API。

### 2. 清理 ES 模块

删除整个 `src/swe/elasticsearch/` 目录：
- `client.py`
- `config.py`
- `__init__.py`

### 3. 清理初始化代码

文件：`src/swe/app/_app.py`

移除 ES 客户端初始化相关代码。

### 4. 清理环境变量

不再需要以下环境变量：
- `SWE_ES_HOST`
- `SWE_ES_PORT`
- `SWE_ES_USER`
- `SWE_ES_ACCESS`
- `SWE_ES_INDEX`

## 清理检查清单

| 文件/目录 | 操作 |
|-----------|------|
| `src/swe/elasticsearch/` | 删除整个目录 |
| `src/swe/app/_app.py` | 移除 ES 初始化 |
| `src/swe/app/runner/runner.py` | 改为调用 Monitor API |
| `src/swe/config/envs/dev.json` | 移除 SWE_ES_* 配置 |
| `src/swe/config/envs/prd.json` | 移除 SWE_ES_* 配置 |
| `tests/unit/elasticsearch/` | 删除测试目录 |

## 环境变量对照

| 用途 | Monitor 环境变量 | 说明 |
|------|------------------|------|
| ES 主机 | `ES_HOST` | 已配置 |
| ES 端口 | `ES_PORT` | 已配置 |
| ES 用户 | `ES_USER` | 已配置 |
| ES 密码 | `ES_PASSWORD` | 已配置 |
| ES 索引 | `ES_INDEX` | 默认值需修正 |

## 迁移步骤

1. 修正 Monitor ES_INDEX 默认值
2. Monitor ES Client 新增 `index_message()` 方法
3. Monitor 新增 `POST /model-output` API
4. SWE runner.py 改为调用 Monitor API
5. 清理 SWE ES 模块代码
6. 清理 SWE 配置文件
7. 删除 SWE ES 测试文件

## 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| Monitor 服务不可用 | model_output 写入失败 | 降级处理，记录日志，不影响主流程 |
| 网络延迟 | 写入耗时增加 | 使用异步调用，不阻塞响应 |

## 验收标准

1. Monitor API 可写入 model_output 到 ES
2. SWE 服务通过 API 写入正常工作
3. SWE 服务无 ES 直连代码
4. 测试全部通过
