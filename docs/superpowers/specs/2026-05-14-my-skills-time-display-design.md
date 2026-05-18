# 我的技能页面时间展示设计

## 背景

"我的技能"页面（应用市场下的 MySkills）当前技能卡片没有展示创建时间和更新时间。用户希望在详情面板中展示这些时间信息，帮助判断技能的活跃度和来源时间。

## 设计决策

### 位置选择：仅详情面板

**排除列表项的理由：**
- 列表项高度约 32px，已有名称 + 最多 3 个标签，空间饱和
- 时间信息属于"元数据层级"，与创建者、类别同级
- 用户浏览列表时主要关注名称和状态，深入查看详情时才关心时间

**详情面板优势：**
- 元数据区域已有"类别"、"创建者"信息，直接追加自然
- 不干扰列表浏览的清爽性
- 信息层级结构清晰

### 展示形式：同行追加

```
┌─────────────────────────────────────────────────────┐
│ 技能名称  [自定义] [接收的] [已禁用]                 │
│ 类别: 数据分析 · 创建者: 张三 · 创建: 3天前 · 更新: 1小时前 │
│ ─────────────────────────────────────────────────── │
│ 描述内容                                             │
└─────────────────────────────────────────────────────┘
```

**时间格式：**
- 默认显示：相对时间（如"3天前"、"刚刚"）
- hover 提示：完整日期时间（如"2025-05-10 14:30:25"）

### 时间字段语义

| 技能类型 | 创建时间来源 | 更新时间来源 |
|----------|-------------|-------------|
| 我创建的 | 用户上传时间 | 用户编辑文件时间 |
| 我接收的 | 分发接收时间 | 用户编辑文件时间 |

**字段命名：**
- `created_at`：技能首次进入用户工作区的时间
- `updated_at`：技能内容最后一次修改的时间

## 实现方案

### 后端修改

#### 1. 数据模型扩展

**文件：** `market/src/market/marketplace/schemas.py`

```python
class MySkillItem(BaseModel):
    """我的技能列表条目."""
    skill_name: str
    display_name: str = ""
    source: str
    description: str = ""
    version: Optional[str] = None
    received_version: Optional[str] = None
    distributed_by: Optional[str] = None
    is_received: bool = False
    has_update: bool = False
    enabled: bool = True
    category: Optional[str] = None
    creator_name: Optional[str] = None
    created_at: Optional[str] = None  # 新增
    updated_at: Optional[str] = None  # 新增
```

#### 2. skill.json 时间字段写入

**场景 A：用户上传技能**

文件：`market/src/market/app/routers/skills_browse.py`
函数：`_update_skill_json` (约第 354 行)

修改内容：
```python
from datetime import datetime, timezone

def _update_skill_json(...):
    ...
    skill_data["source"] = "customized"
    skill_data["creator_id"] = user_id
    skill_data["creator_name"] = user_name
    skill_data["bbk_id"] = bbk_id
    skill_data["created_at"] = datetime.now(timezone.utc).isoformat()  # 新增
    if category_id is not None:
        skill_data["category_id"] = category_id
    ...
```

**场景 B：市场分发技能**

文件：`market/src/market/marketplace/fs.py`
函数：`copy_market_skill_to_user_workspace` (约第 195 行)

修改内容：
```python
skill_data["source"] = f"marketplace:{item_id}"
skill_data["distributed_by"] = distributed_by
skill_data["received_version"] = version
skill_data["created_at"] = datetime.now(timezone.utc).isoformat()  # 新增，代表接收时间
```

**场景 C：用户编辑技能文件**

文件：`market/src/market/app/routers/skills_browse.py`
函数：`save_skill_file` (约第 836 行)

修改内容：
```python
async def save_skill_file(...):
    ...
    # 读取现有 skill.json 并更新 updated_at
    skill_json_path = skill_dir / "skill.json"
    if skill_json_path.exists():
        skill_data = json.loads(skill_json_path.read_text(encoding="utf-8"))
        skill_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        skill_json_path.write_text(json.dumps(skill_data, ensure_ascii=False, indent=2), encoding="utf-8")
    ...
```

#### 3. 读取时间字段

文件：`market/src/market/marketplace/service.py`
函数：`get_my_skills` (约第 911 行)

修改内容：
```python
result.append(
    MySkillItem(
        skill_name=skill_name,
        display_name=display_name,
        source=source,
        description=description,
        version=data.get("version"),
        received_version=received_version,
        distributed_by=data.get("distributed_by"),
        is_received=is_received,
        has_update=has_update,
        enabled=enabled,
        category=data.get("category"),
        creator_name=_decode_creator_name(data.get("creator_name", "")),
        created_at=data.get("created_at"),  # 新增
        updated_at=data.get("updated_at"),  # 新增
    ),
)
```

### 前端修改

#### 1. 类型定义扩展

文件：`console/src/api/modules/mySkills.ts`

```typescript
export interface MySkill {
  skill_name: string;
  display_name: string;
  source: string;
  description: string;
  version: string | null;
  received_version: string | null;
  distributed_by: string | null;
  is_received: boolean;
  has_update: boolean;
  enabled: boolean;
  category?: string;
  creator_name?: string;
  created_at?: string;  // 新增
  updated_at?: string;  // 新增
}
```

#### 2. 详情面板展示

文件：`console/src/pages/MySkills/index.tsx`
组件：`SkillDetailPanel` (约第 642 行)

修改位置：元数据行（约第 689-700 行）

```tsx
import dayjs from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";
dayjs.extend(relativeTime);

// 元数据行修改
<div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
  {skill.category && (
    <Tag style={{ fontSize: 11, borderRadius: 4, backgroundColor: "#f5f5f5", border: "1px solid #d9d9d9" }}>
      {skill.category}
    </Tag>
  )}
  {skill.creator_name && (
    <Text type="secondary" style={{ fontSize: 12 }}>
      创建者: {skill.creator_name}
    </Text>
  )}
  {skill.created_at && (
    <Text type="secondary" style={{ fontSize: 12 }}>
      创建: {dayjs(skill.created_at).fromNow()}
    </Text>
  )}
  {skill.updated_at && (
    <Text type="secondary" style={{ fontSize: 12 }}>
      更新: {dayjs(skill.updated_at).fromNow()}
    </Text>
  )}
</div>
```

**hover 提示实现：**
使用 Tooltip 包裹时间文本，显示完整日期时间。

```tsx
{skill.created_at && (
  <Tooltip title={dayjs(skill.created_at).format("YYYY-MM-DD HH:mm:ss")}>
    <Text type="secondary" style={{ fontSize: 12 }}>
      创建: {dayjs(skill.created_at).fromNow()}
    </Text>
  </Tooltip>
)}
```

## 兼容性考虑

### 已有技能无时间字段

对于在本次修改前已存在的技能，`created_at` 和 `updated_at` 字段为空。

**展示策略：**
- 字段为空时不展示对应时间信息
- 用户编辑旧技能文件后，会写入 `updated_at`，此后开始展示更新时间

**可选：一次性迁移脚本**
可编写脚本扫描所有用户技能目录，根据文件系统时间补全 skill.json 时间字段。但考虑到：
1. 文件系统时间可能不准
2. 迁移成本较高
3. 旧技能展示时间信息价值较低

建议暂不迁移，让时间数据自然累积。

### 单元测试

后端新增测试点：
- `test_update_skill_json_creates_created_at`
- `test_copy_market_skill_creates_created_at`
- `test_save_skill_file_updates_updated_at`
- `test_get_my_skills_includes_time_fields`

前端新增测试点：
- `SkillDetailPanel` 展示时间信息的渲染测试
- 空字段时不渲染对应时间

## 影响范围

| 模块 | 修改文件 | 影响程度 |
|------|----------|----------|
| 后端 Schema | `schemas.py` | 低（仅新增字段） |
| 后端写入逻辑 | `skills_browse.py`, `fs.py` | 中（新增时间写入） |
| 后端读取逻辑 | `service.py` | 低（读取新增字段） |
| 前端类型定义 | `mySkills.ts` | 低（新增类型字段） |
| 前端展示组件 | `index.tsx` | 中（新增展示逻辑） |

## 验收标准

1. 用户上传新技能后，详情面板显示创建时间
2. 管理员分发技能后，接收方详情面板显示创建时间（即接收时间）
3. 用户编辑技能文件后，详情面板显示更新时间
4. hover 时间文本时显示完整日期时间
5. 旧技能（无时间字段）详情面板不显示时间信息，无报错