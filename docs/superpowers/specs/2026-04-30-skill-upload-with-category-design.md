# 技能上传与分类选择设计

> 创建时间：2026-04-30
> 状态：待审核

---

## 一、需求背景

1. **修复 zip 中文文件名解析问题**：当前 market 服务的 zip 解析在处理 Windows 中文编码时有 bug
2. **应用市场上传技能需要选择分类**：Market 页面上传技能时需要弹窗选择分类
3. **我的技能页面直接上传**：MySkills 页面上传技能无需选择分类，直接上传 zip

---

## 二、修复 zip 中文编码

### 问题根因

`market/src/market/app/routers/skills_browse.py` 中 `_extract_zip_skills` 函数：
- `_decode_zip_filename` 函数已正确处理编码转换
- 但 `zf.read(info.filename)` 使用原始编码的文件名读取数据
- 当文件名包含中文时，`info.filename` 是 CP437 编码，导致无法正确匹配 zip 内部的文件索引

### 修复方案

修改 `_extract_zip_skills` 函数，使用 `zf.read(info)` 代替 `zf.read(info.filename)`：

```python
# 修复前
target.write_bytes(zf.read(info.filename))

# 修复后
target.write_bytes(zf.read(info))
```

`zipfile.ZipFile.read()` 方法接受 `ZipInfo` 对象作为参数时，会正确使用内部索引读取数据。

---

## 三、API 设计

### POST /market/skills/upload

新增 `category_id` 参数，用于应用市场上传时指定分类。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file | File | ✓ | zip 文件 |
| category_id | int | - | 分类 ID（Market 上传时必填）|
| enable | bool | - | 是否启用（默认 true）|
| overwrite | bool | - | 是否覆盖（默认 false）|
| target_name | str | - | 重命名技能名称 |

### 响应 Schema

```python
class UploadSkillResponse(BaseModel):
    imported: list[str]
    count: int
    enabled: bool
    name: str | None = None      # 解析出的技能名称
    description: str | None = None  # 解析出的描述
    conflicts: list[dict] | None = None
```

---

## 四、前端组件设计

### 4.1 应用市场上传弹窗

**文件位置：** `console/src/pages/Market/components/UploadSkillModal.tsx`

**组件结构：**

```
┌─────────────────────────────────────────────┐
│  上传技能到市场                              │
├─────────────────────────────────────────────┤
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │     拖拽 .zip 文件到此处              │   │
│  │        或点击选择文件                 │   │
│  │     支持: .zip (含 SKILL.md)          │   │
│  └─────────────────────────────────────┘   │
│                                             │
│  技能分类 *                                  │
│  ┌─────────────────────────────────────┐   │
│  │  选择分类                       ▼   │   │
│  └─────────────────────────────────────┘   │
│                                             │
│  ─────────────────────────────────────────  │
│  提示：技能名称和描述将从 zip 包中的        │
│       SKILL.md frontmatter 自动解析         │
│                                             │
├─────────────────────────────────────────────┤
│                    [取消]  [上传]           │
└─────────────────────────────────────────────┘
```

**交互流程：**

1. 用户点击"上传技能"按钮 → 打开弹窗
2. 用户拖拽或选择 zip 文件
3. 用户从下拉框选择分类（必填）
4. 点击"上传"按钮 → 调用 API
5. 成功后关闭弹窗，刷新列表，提示成功

### 4.2 我的技能页面上传

**文件位置：** `console/src/pages/MySkills/index.tsx`

当前已有上传逻辑（`handleFileSelect`），无需弹窗选择分类，保持现有行为：
- 点击"上传技能"按钮 → 直接选择 zip 文件
- 上传成功后刷新列表

---

## 五、文件变更清单

### 需新增的文件

| 文件 | 说明 |
|------|------|
| `console/src/pages/Market/components/UploadSkillModal.tsx` | 应用市场上传弹窗组件 |

### 需修改的文件

| 文件 | 修改内容 |
|------|----------|
| `market/src/market/app/routers/skills_browse.py` | 修复 zip 编码；upload API 新增 category_id 参数 |
| `market/src/market/marketplace/schemas.py` | 新增 UploadSkillResponse schema |
| `console/src/pages/Market/MarketSkills.tsx` | 引入弹窗，修改上传按钮逻辑 |
| `console/src/api/modules/market.ts` | uploadSkillToWorkspace 新增 category_id 参数 |

---

## 六、日志记录

| 操作 | 日志表 | 说明 |
|------|--------|------|
| MySkills 上传技能 | `swe_user_item_operation_logs` | 用户创建自己的技能 |
| Market 上传技能 | `swe_marketplace_operation_logs` | 管理员发布公共技能到市场 |

---

## 七、验证方式

1. 启动 Market 服务
2. 测试 zip 中文文件名上传：
   - 准备包含中文文件名的 zip 包
   - 上传并验证文件正确解压
3. 测试应用市场上传：
   - 打开弹窗，选择分类
   - 上传 zip，验证分类正确记录
4. 测试我的技能上传：
   - 直接上传 zip，验证无需选择分类