# 技能菜单功能迁移规格说明

## 一、背景与目标

### 1.1 当前状态

项目存在两套技能管理功能：

| 服务 | 目录 | 功能定位 |
|------|------|----------|
| **src/swe** | `src/swe/app/routers/skills.py` | Agent 工作空间技能管理、技能池管理、Hub 导入 |
| **market** | `market/src/market/app/routers/skills_browse.py` | 市场技能浏览、用户技能管理（我的技能） |

**问题：**
1. 两套功能存在重叠（启用/禁用/删除技能）
2. 前端需要调用两套 API（`/skills/*` 和 `/market/skills/*`）
3. 用户技能管理分散在两个入口

### 1.2 迁移目标

将 `src/swe` 中的**技能菜单相关功能**迁移到 `market` 服务：

1. **统一用户技能管理入口**：用户技能的 CRUD 操作统一由 market 服务处理
2. **保留 src/swe 核心能力**：Agent 运行时技能加载、技能池管理、Hub 导入
3. **明确服务边界**：减少功能重叠，降低维护成本

### 1.3 迁移范围

| 功能 | 当前位置 | 迁移后位置 | 说明 |
|------|----------|------------|------|
| 工作空间技能列表 | `src/swe` → `/skills` | 保留 | Agent 运行时需要 |
| 技能启用/禁用 | `src/swe` + `market` | `market` | 统一到 market |
| 技能创建/删除 | `src/swe` + `market` | `market` | 统一到 market |
| 技能文件编辑 | `src/swe` + `market` | `market` | 统一到 market |
| 技能池管理 | `src/swe` | 保留 | 管理员功能 |
| Hub 导入 | `src/swe` | 保留 | 需要运行时集成 |
| 市场技能浏览 | `market` | 保留 | market 核心功能 |

---

## 二、架构设计

### 2.1 服务边界定义

```
┌─────────────────────────────────────────────────────────────────┐
│                         Console Frontend                         │
├─────────────────────────────────────────────────────────────────┤
│  /my-skills          │  /agent/skills      │  /skill-pool       │
│  (我的技能)          │  (工作空间技能)      │  (技能池)          │
└──────────┬───────────┴──────────┬──────────┴──────────┬─────────┘
           │                      │                     │
           ▼                      ▼                     ▼
┌──────────────────────┐  ┌──────────────────────┐  ┌─────────────┐
│   Market Service     │  │     SWE Service      │  │ SWE Service │
│  /market/skills/*    │  │    /skills/*         │  │ /skills/pool│
├──────────────────────┤  ├──────────────────────┤  ├─────────────┤
│ • 我的技能 CRUD      │  │ • 工作空间技能列表   │  │ • 技能池管理│
│ • 启用/禁用          │  │ • 技能状态查询       │  │ • Hub 导入  │
│ • 文件编辑           │  │ • 技能加载(运行时)   │  │ • 广播分发  │
│ • 市场浏览           │  │                      │  │             │
└──────────┬───────────┘  └──────────┬───────────┘  └──────┬──────┘
           │                         │                     │
           │    HTTP Callback        │                     │
           │  (Agent Reload)         │                     │
           └────────────────────────►┘                     │
                    POST /api/internal/agents/{id}/reload   │
                                                           │
┌──────────────────────────────────────────────────────────┴─────────┐
│                     Shared File System                              │
│  <swe_root>/<user_id>/workspaces/<agent_id>/skills/<skill_name>/   │
│  <swe_root>/<user_id>/workspaces/<agent_id>/skill.json             │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 API 职责划分

#### Market Service API（用户技能管理）

| 端点 | 方法 | 说明 |
|------|------|------|
| `/market/skills/mine` | GET | 我创建的技能列表 |
| `/market/skills/received` | GET | 我接收的技能列表 |
| `/market/skills/upload` | POST | 上传技能到工作区 |
| `/market/skills/mine/{name}` | DELETE | 删除技能 |
| `/market/skills/mine/{name}/enable` | POST | 启用技能 |
| `/market/skills/mine/{name}/disable` | POST | 禁用技能 |
| `/market/skills/mine/{name}/files` | GET | 获取技能文件树 |
| `/market/skills/mine/{name}/files/{path}` | GET/PUT | 读写技能文件 |
| `/market/skills/mine/batch-*` | POST | 批量操作 |

#### SWE Service API（运行时支持）

| 端点 | 方法 | 说明 |
|------|------|------|
| `/skills` | GET | 工作空间技能列表（含状态） |
| `/skills/refresh` | POST | 强制同步技能状态 |
| `/skills/pool/*` | * | 技能池管理（管理员） |
| `/skills/hub/*` | * | Hub 导入 |
| `/api/internal/agents/{id}/reload` | POST | 内部重载回调 |

### 2.3 服务间通信

#### 已有通信机制

Market → SWE 的 HTTP 回调：

```python
# market/src/market/marketplace/service.py
async def _trigger_agent_reload(self, user_id: str, agent_id: str = "default"):
    url = f"{SWE_INTERNAL_URL}/api/internal/agents/{agent_id}/reload"
    headers = {}
    if SWE_INTERNAL_TOKEN:
        headers["X-Internal-Token"] = f"Bearer {SWE_INTERNAL_TOKEN}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(url, params={"tenant_id": user_id}, headers=headers)
```

配置项：
- `SWE_INTERNAL_URL`: SWE 服务内部地址（默认 `http://localhost:8000`）
- `SWE_INTERNAL_TOKEN`: 内部服务认证 Token（可选）

#### 通信时机

| 触发操作 | 通信内容 | 目的 |
|----------|----------|------|
| 启用技能 | POST reload | 重新加载 Agent 技能配置 |
| 禁用技能 | POST reload | 重新加载 Agent 技能配置 |
| 批量启用/禁用 | POST reload | 重新加载 Agent 技能配置 |

---

## 三、迁移方案

### 3.1 阶段一：功能对齐（当前已完成）

Market 服务已具备完整的用户技能管理能力：
- ✅ 启用/禁用技能（含安全扫描）
- ✅ 删除技能
- ✅ 批量操作
- ✅ 文件树浏览与编辑
- ✅ Agent 重载回调

### 3.2 阶段二：前端整合

#### 3.2.1 统一技能入口

**当前状态：**
- `/agent/skills`: 调用 `/skills/*` API（SWE）
- `/my-skills`: 调用 `/market/skills/*` API（Market）

**整合方案：**

| 页面 | 功能 | API 来源 |
|------|------|----------|
| `/my-skills` | 我的技能（用户视角） | Market API |
| `/agent/skills` | 工作空间技能（Agent 视角） | SWE API（只读） |
| `/skill-pool` | 技能池（管理员） | SWE API |

#### 3.2.2 功能迁移清单

**从 SWE 技能页面移除的功能：**
1. 技能创建 → 引导到 `/my-skills` 或 `/skill-pool`
2. 技能删除 → 引导到 `/my-skills`
3. 技能启用/禁用 → 引导到 `/my-skills`
4. 技能编辑 → 引导到 `/my-skills`

**保留在 SWE 技能页面的功能：**
1. 技能列表展示（只读）
2. 技能状态查看
3. 技能池下载到工作空间
4. Hub 导入

### 3.3 阶段三：清理冗余代码

#### 3.3.1 SWE 服务清理

**保留的端点：**
```
GET  /skills                    # 工作空间技能列表
POST /skills/refresh            # 强制同步
GET  /skills/workspaces         # 多工作空间视图
GET  /skills/pool/*             # 技能池管理
POST /skills/pool/download      # 从池下载到工作空间
GET  /skills/hub/*              # Hub 导入
POST /skills/hub/install/*      # Hub 安装任务
```

**移除的端点（迁移到 Market）：**
```
POST   /skills                  # 创建技能 → Market
POST   /skills/upload           # 上传技能 → Market
PUT    /skills/save             # 保存技能 → Market
DELETE /skills/{name}           # 删除技能 → Market
POST   /skills/{name}/enable    # 启用技能 → Market
POST   /skills/{name}/disable   # 禁用技能 → Market
POST   /skills/batch-enable     # 批量启用 → Market
POST   /skills/batch-disable    # 批量禁用 → Market
POST   /skills/batch-delete     # 批量删除 → Market
GET    /skills/{name}/files/*   # 文件访问 → Market
PUT    /skills/{name}/config    # 配置更新 → Market
```

#### 3.3.2 前端清理

**`console/src/api/modules/skill.ts` 清理：**
- 移除：`createSkill`, `saveSkill`, `deleteSkill`, `enableSkill`, `disableSkill`
- 移除：`batchEnableSkills`, `batchDeleteSkills`, `uploadSkill`
- 保留：`listSkills`, `refreshSkills`, `listSkillWorkspaces`
- 保留：所有 `*PoolSkill*` 方法
- 保留：所有 `*Hub*` 方法

---

## 四、数据一致性保障

### 4.1 共享文件系统

两个服务访问同一目录：

```
<swe_root>/<user_id>/workspaces/<agent_id>/
├── skills/
│   └── <skill_name>/
│       ├── SKILL.md
│       ├── skill.json        # 技能元数据
│       └── ...
└── skill.json                # 工作空间技能清单（启用状态）
```

### 4.2 状态同步机制

**skill.json 清单结构：**
```json
{
  "schema_version": "workspace-skill-manifest.v1",
  "version": 0,
  "skills": {
    "my_skill": {
      "enabled": true,
      "channels": ["all"],
      "config": {},
      "updated_at": "2026-05-01T00:00:00Z"
    }
  }
}
```

**原子写入机制：**
```python
# market/src/market/marketplace/fs.py
def _atomic_write_json(path: Path, data: dict) -> None:
    dir_ = path.parent
    dir_.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dir_, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)  # 原子替换
    except Exception:
        os.unlink(tmp_path)
        raise
```

### 4.3 Agent 重载时机

```
Market API 调用
    ↓
更新 skill.json（原子写入）
    ↓
HTTP 回调 SWE /api/internal/agents/{id}/reload
    ↓
SWE Agent 重新加载技能配置
    ↓
响应返回前端
```

**重载失败处理：**
- 前端显示成功（文件已更新）
- 后台记录警告日志
- Agent 下次请求时自动加载最新配置

---

## 五、安全考虑

### 5.1 安全扫描

两个服务都使用相同的 `scan_skill_directory` 函数：

**扫描时机：**
- Market：启用技能前扫描
- SWE：Hub 导入时扫描

**扫描规则位置：**
- `src/swe/security/skill_scanner/`
- `market/src/market/security/skill_scanner/`（需保持同步）

### 5.2 内部服务认证

```python
# src/swe/app/routers/internal.py
_INTERNAL_TOKEN = os.environ.get("SWE_INTERNAL_TOKEN", "")

def _verify_internal_token(token: Optional[str]) -> None:
    if _INTERNAL_TOKEN:
        if not token or token != f"Bearer {_INTERNAL_TOKEN}":
            raise HTTPException(status_code=401, detail="Unauthorized")
```

**配置建议：**
- 生产环境必须配置 `SWE_INTERNAL_TOKEN`
- 使用强随机字符串（至少 32 字符）

---

## 六、前端改造

### 6.1 页面职责划分

| 页面 | 路由 | 职责 | 主要 API |
|------|------|------|----------|
| 我的技能 | `/my-skills` | 用户技能 CRUD | Market API |
| 工作空间技能 | `/agent/skills` | 技能状态查看 | SWE API（只读） |
| 技能池 | `/skill-pool` | 管理员管理共享技能 | SWE API |

### 6.2 导航调整

**当前侧边栏结构：**
```
├── 工作空间
│   └── 技能管理 (/agent/skills)  # 功能完整
├── 设置
│   └── 技能池 (/skill-pool)      # 管理员
```

**调整后结构：**
```
├── 我的技能 (/my-skills)          # 用户技能入口（新建）
├── 工作空间
│   └── 技能管理 (/agent/skills)  # 只读查看 + 池下载
├── 设置
│   └── 技能池 (/skill-pool)      # 管理员
```

### 6.3 API 调用迁移

**`/agent/skills` 页面改造：**

| 操作 | 当前 | 改造后 |
|------|------|--------|
| 查看技能列表 | `skillApi.listSkills()` | 保持 |
| 创建技能 | `skillApi.createSkill()` | 跳转到 `/my-skills` |
| 上传技能 | `skillApi.uploadSkill()` | 跳转到 `/my-skills` |
| 启用/禁用 | `skillApi.enableSkill()` | 跳转到 `/my-skills` |
| 删除技能 | `skillApi.deleteSkill()` | 跳转到 `/my-skills` |
| 从池下载 | `skillApi.downloadSkillPoolSkill()` | 保持 |
| Hub 导入 | `skillApi.startHubSkillInstall()` | 保持 |

---

## 七、实施计划

### Phase 1: 准备工作（1 天）

1. 确认 Market 服务功能完整性
2. 验证 HTTP 回调机制可靠性
3. 同步安全扫描规则

### Phase 2: 前端整合（2-3 天）

1. 创建/完善 `/my-skills` 页面
2. 改造 `/agent/skills` 为只读视图
3. 调整侧边栏导航
4. 更新 API 调用

### Phase 3: 后端清理（1 天）

1. 移除 SWE 服务冗余端点
2. 清理前端冗余 API 方法
3. 更新 API 类型定义

### Phase 4: 测试与验证（1 天）

1. 端到端功能测试
2. 服务间通信测试
3. 安全扫描测试
4. 回归测试

---

## 八、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| HTTP 回调失败 | Agent 未重载 | 1. 添加重试机制 2. Agent 启动时自动同步 |
| 文件写入冲突 | 数据损坏 | 使用原子写入机制 |
| 安全扫描不一致 | 绕过检查 | 统一扫描模块，定期同步 |
| 前端路由变更 | 用户困惑 | 添加引导提示，保留旧路由重定向 |

---

## 九、附录

### A. 关键文件清单

| 文件 | 说明 |
|------|------|
| `src/swe/app/routers/skills.py` | SWE 技能 API（待精简） |
| `src/swe/app/routers/internal.py` | 内部回调端点 |
| `src/swe/agents/skills_manager.py` | 技能管理服务层 |
| `market/src/market/app/routers/skills_browse.py` | Market 用户技能 API |
| `market/src/market/marketplace/service.py` | Market 服务层（含回调） |
| `market/src/market/marketplace/fs.py` | 文件系统工具 |
| `console/src/api/modules/skill.ts` | SWE API 客户端 |
| `console/src/api/modules/mySkills.ts` | Market API 客户端 |
| `console/src/pages/Agent/Skills/index.tsx` | 工作空间技能页面 |
| `console/src/pages/MySkills/index.tsx` | 我的技能页面 |

### B. 配置项

| 配置 | 位置 | 说明 |
|------|------|------|
| `SWE_INTERNAL_URL` | Market 环境变量 | SWE 服务内部地址 |
| `SWE_INTERNAL_TOKEN` | 双方环境变量 | 内部服务认证 Token |
