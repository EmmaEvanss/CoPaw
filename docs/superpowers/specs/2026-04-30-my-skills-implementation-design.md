# 我的技能页面实现设计文档

> 创建时间：2026-04-30
> 状态：待审核
> 基于：2026-04-29-marketplace-design.md

---

## 一、实现范围

本次实现分两个阶段，第一阶段先实现核心功能：

### 第一阶段（本次实现）

| 功能 | 我创建的 | 我接收的 |
|------|----------|----------|
| 树形文件浏览 | ✓ | ✓ |
| 文件内容预览 | ✓ | ✓ |
| 编辑文件 | ✓ | ✗ |
| 启用/禁用 | ✓ | ✓ |
| 删除（单个） | ✓ | ✓ |
| 批量删除 | ✓ | ✓ |

### 第二阶段（后续迭代）

| 功能 | 我创建的 | 我接收的 |
|------|----------|----------|
| 发布到市场 | ✓（仅管理员） | ✗ |
| 更新（拉取市场最新版本） | ✗ | ✓ |
| 创建新技能 | ✓ | ✗ |

---

## 二、架构设计

### 整体布局

```
┌─────────────────────────────────────────────────────────┐
│                    MySkills 页面                          │
├──────────────────────┬──────────────────────────────────┤
│   左侧面板 (300px)    │        右侧详情面板               │
│  ┌────────────────┐  │  ┌─────────────────────────────┐ │
│  │ 搜索框 + 按钮   │  │  │ 技能头部：名称、版本、标签   │ │
│  ├────────────────┤  │  ├─────────────────────────────┤ │
│  │ 我创建的 (折叠) │  │  │ 描述                        │ │
│  │  └─ 技能条目    │  │  ├─────────────────────────────┤ │
│  │     └─ 文件树   │  │  │ 文件内容预览/编辑区         │ │
│  ├────────────────┤  │  └─────────────────────────────┘ │
│  │ 我接收的 (折叠) │  │                                  │
│  │  └─ 技能条目    │  │  操作栏：启用/禁用、删除        │
│  │     └─ 文件树   │  │                                  │
│  └────────────────┘  │                                  │
└──────────────────────┴──────────────────────────────────┘
```

### 数据流

```
页面加载 → GET /market/skills/mine + /market/skills/received → 技能列表
点击技能 → GET /market/skills/mine/{skill_name}/files → 文件树
点击文件 → GET /market/skills/mine/{skill_name}/files/{path} → 文件内容
编辑保存 → PUT /market/skills/mine/{skill_name}/files/{path} → 更新文件
删除技能 → DELETE /market/skills/mine/{skill_name} → 删除 + 刷新列表
启用/禁用 → POST /market/skills/mine/{skill_name}/enable|disable → 更新状态
```

---

## 三、前端组件设计

### 组件职责

| 组件 | 职责 | 文件路径 |
|------|------|----------|
| `index.tsx` | 主页面布局、状态管理 | `console/src/pages/MySkills/index.tsx` |
| `SkillSection.tsx` | 分组容器（我创建的/我接收的） | `console/src/pages/MySkills/components/SkillSection.tsx` |
| `SkillItem.tsx` | 单个技能条目，含展开折叠 | `console/src/pages/MySkills/components/SkillItem.tsx` |
| `SkillFileTree.tsx` | 递归渲染文件树 | `console/src/pages/MySkills/components/SkillFileTree.tsx` |
| `SkillDetail.tsx` | 右侧详情面板 | `console/src/pages/MySkills/components/SkillDetail.tsx` |
| `SkillFileEditor.tsx` | 文件编辑器 | `console/src/pages/MySkills/components/SkillFileEditor.tsx` |

### 核心状态

```typescript
// 数据状态
const [skills, setSkills] = useState<MySkill[]>([]);
const [skillFiles, setSkillFiles] = useState<Record<string, FileTreeNode[]>>({});
const [selectedSkill, setSelectedSkill] = useState<MySkill | null>(null);
const [selectedFile, setSelectedFile] = useState<string | null>(null);
const [fileContent, setFileContent] = useState<string | null>(null);

// UI 状态
const [expandedSkills, setExpandedSkills] = useState<Set<string>>(new Set());
const [expandedDirs, setExpandedDirs] = useState<Set<string>>(new Set());
const [disabledSkills, setDisabledSkills] = useState<Set<string>>(new Set());
const [batchMode, setBatchMode] = useState<boolean>(false);
const [selectedForBatch, setSelectedForBatch] = useState<Set<string>>(new Set());
```

---

## 四、后端 API 设计

### 新增端点（Market 服务）

| 方法 | 路径 | 说明 | 请求头 |
|------|------|------|--------|
| `GET` | `/market/skills/mine/{skill_name}/files` | 获取技能文件树 | X-Source-Id, X-User-Id, X-User-Name, X-Bbk-Id |
| `GET` | `/market/skills/mine/{skill_name}/files/{file_path:path}` | 读取文件内容 | X-Source-Id, X-User-Id, X-User-Name, X-Bbk-Id |
| `PUT` | `/market/skills/mine/{skill_name}/files/{file_path:path}` | 保存文件内容 | X-Source-Id, X-User-Id, X-User-Name, X-Bbk-Id |
| `DELETE` | `/market/skills/mine/{skill_name}` | 删除技能 | X-Source-Id, X-User-Id, X-User-Name, X-Bbk-Id |
| `POST` | `/market/skills/mine/{skill_name}/enable` | 启用技能 | X-Source-Id, X-User-Id, X-User-Name, X-Bbk-Id |
| `POST` | `/market/skills/mine/{skill_name}/disable` | 禁用技能 | X-Source-Id, X-User-Id, X-User-Name, X-Bbk-Id |

### 响应 Schema

```python
# 文件树节点
class FileTreeNode(BaseModel):
    name: str
    type: Literal["file", "directory"]
    path: str
    children: list["FileTreeNode"] | None = None

# 文件内容响应
class FileContentResponse(BaseModel):
    content: str
    file_type: str  # "markdown" | "json" | "text" | "binary"

# 操作结果响应
class OperationResponse(BaseModel):
    success: bool
    message: str | None = None
```

### 后端实现位置

- 路由：`market/src/market/app/routers/skills_browse.py`
- 服务层：`market/src/market/marketplace/service.py`
- 文件系统：复用 `market/src/market/marketplace/fs.py`

---

## 五、前端 API 模块设计

### 扩展 `console/src/api/modules/mySkills.ts`

```typescript
export const mySkillsApi = {
  // 现有方法
  getCreatedSkills: (sourceId, userId) => ...,
  getReceivedSkills: (sourceId, userId) => ...,

  // 新增方法
  listSkillFiles: async (
    sourceId: string,
    userId: string,
    userName: string,
    bbkId: string,
    skillName: string
  ): Promise<FileTreeNode[]>,

  readSkillFile: async (
    sourceId: string,
    userId: string,
    userName: string,
    bbkId: string,
    skillName: string,
    filePath: string
  ): Promise<{ content: string; fileType: string }>,

  saveSkillFile: async (
    sourceId: string,
    userId: string,
    userName: string,
    bbkId: string,
    skillName: string,
    filePath: string,
    content: string
  ): Promise<void>,

  deleteSkill: async (
    sourceId: string,
    userId: string,
    userName: string,
    bbkId: string,
    skillName: string
  ): Promise<void>,

  enableSkill: async (...) => Promise<void>,
  disableSkill: async (...) => Promise<void>,
};
```

### 错误处理

| 错误码 | 场景 | 用户提示 |
|--------|------|----------|
| 404 | 文件不存在 | "文件不存在" |
| 403 | 编辑接收的技能 | "只有我创建的技能支持编辑" |
| 400 | 文件过大 | "文件过大，不支持在线预览" |

---

## 六、文件类型处理

### 支持的预览类型

| 类型 | 扩展名 | 预览方式 | 可编辑 |
|------|--------|----------|--------|
| Markdown | `.md` | ReactMarkdown 渲染 | ✓（我创建的） |
| JSON | `.json` | 格式化展示 | ✓（我创建的） |
| 文本 | `.txt`, `.yaml`, `.py`, `.sh` 等 | 代码展示 | ✓（我创建的） |
| 图片 | `.png`, `.jpg`, `.gif` | 图片预览 | ✗ |
| PDF | `.pdf` | iframe 嵌入 | ✗ |
| 其他 | 其他扩展名 | 提示不支持预览 | ✗ |

### 文件树排序

1. `SKILL.md` 置顶
2. `skill.json` 次之
3. `references/` 目录
4. `scripts/` 目录
5. 其他按字母顺序

### Markdown 编辑特殊处理

- SKILL.md 含 YAML frontmatter 时，编辑时只编辑正文
- frontmatter 受保护不可修改
- 保存时自动合并 frontmatter + 正文

---

## 七、批量操作设计

### UI 流程

1. 顶部"批量管理"按钮 → 进入批量模式
2. 技能条目前显示复选框 → 勾选多个
3. 底部显示"已选择 N 个" + 批量删除按钮
4. 点击删除 → 确认弹窗
5. 确认 → 逐个调用 DELETE API → 刷新列表 → 退出批量模式

### 禁用状态管理

```typescript
// 存储在 localStorage
const DISABLED_SKILLS_KEY = "copaw_disabled_skills";

// 获取/设置禁用列表
function getDisabledSkills(): Set<string>;
function toggleSkillDisabled(skillName: string, disabled: boolean);
```

---

## 八、关键文件清单

### 需新增的文件

| 类型 | 文件路径 |
|------|----------|
| 前端组件 | `console/src/pages/MySkills/components/SkillSection.tsx` |
| 前端组件 | `console/src/pages/MySkills/components/SkillItem.tsx` |
| 前端组件 | `console/src/pages/MySkills/components/SkillFileTree.tsx` |
| 前端组件 | `console/src/pages/MySkills/components/SkillDetail.tsx` |
| 前端组件 | `console/src/pages/MySkills/components/SkillFileEditor.tsx` |

### 需修改的文件

| 文件路径 | 修改内容 |
|----------|----------|
| `console/src/pages/MySkills/index.tsx` | 重构为新的组件结构 |
| `console/src/api/modules/mySkills.ts` | 新增 API 方法 |
| `market/src/market/app/routers/skills_browse.py` | 新增 API 端点 |
| `market/src/market/marketplace/service.py` | 新增文件操作方法 |
| `market/src/market/marketplace/schemas.py` | 新增响应 Schema |

---

## 九、验证方式

### 前端验证

1. 启动 Console 开发服务器：`pnpm dev`
2. 访问 `/my-skills` 页面
3. 测试功能：
   - 技能列表展示和折叠
   - 文件树展开和文件选择
   - 文件内容预览（Markdown 渲染、JSON 展示）
   - 编辑文件并保存（我创建的技能）
   - 启用/禁用切换
   - 单个删除和批量删除

### 后端验证

1. 启动 Market 服务
2. 使用 curl 或 Postman 测试 API：
   - 文件树获取
   - 文件内容读取
   - 文件保存
   - 删除、启用、禁用操作

---

## 十、后续迭代

第二阶段将实现：
- 发布到市场（仅管理员可见，我创建的技能支持）
- 更新功能（我接收的技能拉取市场最新版本）
- 创建新技能表单

设计文档将在迭代时扩展。