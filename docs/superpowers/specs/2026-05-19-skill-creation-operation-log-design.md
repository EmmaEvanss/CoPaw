# 技能创建操作日志设计方案

## 需求背景

用户通过对话让 Agent 调用 `skill_creator` 技能创建新技能。需要将此操作记录到 `swe_user_item_operation_logs` 表，用于：
- 追踪用户创建了哪些技能
- 统计用户操作行为
- 审计和合规需求

## 设计方案

### 核心思路

Agent 完成技能创建后，主动调用 market 服务的 API 上报操作日志。采用"失败忽略"策略，确保日志记录对主流程性能影响最小。

### 架构设计

```text
用户对话请求
    ↓
Agent 调用 skill_creator 技能
    ↓
Agent 按步骤创建技能（写文件）
    ↓
Agent 调用日志上报 API
    ↓
market 服务写入 swe_user_item_operation_logs 表
    （失败仅记录警告，不影响业务）
```

### 数据模型

复用现有表 `swe_user_item_operation_logs`：

| 字段 | 值 | 说明 |
|------|-----|------|
| source_id | 请求来源标识 | 如 "console"、"api" |
| operator_id | 用户 ID | 执行创建操作的用户 |
| operator_name | 用户名称 | 可选 |
| operation | "create" | 操作类型 |
| item_type | "skill" | 条目类型 |
| item_id | "" | 可为空 |
| item_name | 技能名称 | 创建的技能名 |
| target_user_id | 用户 ID | 同 operator_id |
| target_user_name | 用户名称 | 同 operator_name |
| target_bbk_id | 机构 ID | 可选 |

### API 设计

**端点**：扩展现有日志记录逻辑

**位置**：`market/src/market/app/routers/skills_browse.py`

**请求方式**：POST

**路径**：`/market/skills/operation-log`

**请求体**：
```json
{
  "source_id": "console",
  "operator_id": "user123",
  "operator_name": "张三",
  "operation": "create",
  "item_type": "skill",
  "item_name": "my_new_skill",
  "target_bbk_id": null
}
```

**响应**：
```json
{
  "success": true
}
```

**错误处理**：写入失败返回 `{"success": false}`，但不抛异常，仅记录警告日志。

### skill_creator 文档修改

在 `skill_creator/SKILL.md` 步骤 5 后新增步骤 6：

```markdown
### 步骤 6：上报操作日志

技能创建完成后，需要上报操作日志以记录此次创建行为。

使用 `execute_shell_command` 调用日志上报 API：

```bash
curl -X POST "http://localhost:8000/market/skills/operation-log" \
  -H "Content-Type: application/json" \
  -H "X-User-Id: <当前用户ID>" \
  -d '{
    "source_id": "console",
    "operator_id": "<当前用户ID>",
    "operator_name": "<当前用户名称>",
    "operation": "create",
    "item_type": "skill",
    "item_name": "<创建的技能名称>",
    "target_bbk_id": null
  }'
```

**注意**：
- 日志上报失败不影响技能创建结果
- 如果 API 调用失败，记录警告即可，无需重试
```

### 性能考虑

1. **失败忽略**：日志写入失败仅记录警告，不抛异常，不阻塞主流程
2. **无异步依赖**：直接写入数据库，无需消息队列等额外基础设施
3. **轻量请求**：API 仅做单条 INSERT，响应时间毫秒级
4. **现有实践**：与 `skills_browse.py` 中上传技能的日志记录方式一致

### 实现步骤

1. **market 服务**：在 `skills_browse.py` 新增 `/operation-log` 端点
2. **skill_creator**：修改 `SKILL.md`，增加步骤 6
3. **测试**：验证日志记录正确性

### 验收标准

1. Agent 创建技能后，`swe_user_item_operation_logs` 表有对应记录
2. 日志写入失败不影响技能创建
3. 日志记录包含用户 ID、技能名称等关键信息

## 风险与缓解

| 风险 | 缓解措施 |
|------|---------|
| Agent 可能遗漏上报 | 文档中强调必要性，后续可考虑抽取为工具 |
| API 地址需配置 | 使用环境变量或配置管理 API 基础地址 |
| 用户信息获取 | Agent 从上下文中获取当前用户信息 |

## 后续演进

如果未来需要支持更多操作类型（如 edit、delete）或更多场景需要上报日志，可考虑：
1. 抽取为通用工具函数
2. 定义操作类型枚举
3. 扩展 API 支持更多操作类型
