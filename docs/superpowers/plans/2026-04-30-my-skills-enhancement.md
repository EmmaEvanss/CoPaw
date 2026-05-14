# 我的技能页面功能增强实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完善"我的技能"页面，实现树形文件浏览、文件内容预览编辑、删除、启用/禁用等核心功能。

**Architecture:** 前端参照 CmbCoworkAgent 的 SkillsPanel 组件结构，后端在 Market 服务新增技能文件操作 API。

**Tech Stack:** React 18, TypeScript, Ant Design 5, Python 3.10+, FastAPI

---

## 文件结构

| 文件 | 操作 | 说明 |
|------|------|------|
| `market/src/market/marketplace/schemas.py` | Modify | 新增 FileTreeNode、FileContentResponse |
| `market/src/market/marketplace/service.py` | Modify | 新增 list_skill_files、read_skill_file、save_skill_file、delete_skill 方法 |
| `market/src/market/app/routers/skills_browse.py` | Modify | 新增文件操作和删除 API |
| `console/src/api/modules/mySkills.ts` | Modify | 新增文件操作和删除 API 方法 |
| `console/src/pages/MySkills/index.tsx` | Rewrite | 重构为新布局 |
| `console/src/pages/MySkills/components/SkillSection.tsx` | Create | 分组容器 |
| `console/src/pages/MySkills/components/SkillItem.tsx` | Create | 技能条目（含文件树） |
| `console/src/pages/MySkills/components/SkillFileTree.tsx` | Create | 文件树组件 |
| `console/src/pages/MySkills/components/SkillDetail.tsx` | Create | 详情面板 |
| `console/src/pages/MySkills/components/SkillFileEditor.tsx` | Create | 文件编辑器 |

---

### Task 1: 后端 Schema 扩展

**Files:**
- Modify: `market/src/market/marketplace/schemas.py`

- [ ] **Step 1: 添加文件相关 Schema**

在 `market/src/market/marketplace/schemas.py` 末尾添加：

```python
class FileTreeNode(BaseModel):
    """文件树节点."""
    name: str
    type: Literal["file", "directory"]
    path: str
    children: list["FileTreeNode"] | None = None


class FileContentResponse(BaseModel):
    """文件内容响应."""
    content: str
    file_type: str  # "markdown" | "json" | "text" | "binary"


class OperationResponse(BaseModel):
    """操作结果响应."""
    success: bool = True
    message: str | None = None
```

需要添加 import：
```python
from typing import Literal, Optional
```

- [ ] **Step 2: Commit**

```bash
git add market/src/market/marketplace/schemas.py
git commit -m "feat(market): add FileTreeNode and file operation schemas"
```

---

### Task 2: 后端 Service 文件操作方法

**Files:**
- Modify: `market/src/market/marketplace/service.py`

- [ ] **Step 1: 添加 list_skill_files 方法**

在 `MarketplaceService` 类中添加：

```python
    def list_skill_files(
        self,
        user_id: str,
        skill_name: str,
        agent_id: str = "default",
    ) -> list[dict]:
        """列出技能文件树."""
        from .fs import get_user_skills_dir

        skills_dir = get_user_skills_dir(self.swe_root, user_id, agent_id)
        skill_dir = skills_dir / skill_name
        if not skill_dir.exists():
            return []

        def build_tree(path: Path, base: Path) -> dict:
            relative = path.relative_to(base)
            if path.is_file():
                return {
                    "name": path.name,
                    "type": "file",
                    "path": str(relative),
                }
            children = []
            for child in sorted(path.iterdir()):
                if child.name.startswith("."):
                    continue
                children.append(build_tree(child, base))
            return {
                "name": path.name,
                "type": "directory",
                "path": str(relative),
                "children": children,
            }

        # 排序：SKILL.md 置顶，skill.json 次之，然后目录，最后其他文件
        items = list(skill_dir.iterdir())
        items.sort(key=lambda p: (
            0 if p.name == "SKILL.md" else
            1 if p.name == "skill.json" else
            2 if p.is_dir() else 3,
            p.name.lower()
        ))

        return [build_tree(item, skill_dir) for item in items if not item.name.startswith(".")]
```

- [ ] **Step 2: 添加 read_skill_file 方法**

```python
    def read_skill_file(
        self,
        user_id: str,
        skill_name: str,
        file_path: str,
        agent_id: str = "default",
    ) -> tuple[str | None, str]:
        """读取技能文件内容，返回 (content, file_type)."""
        from .fs import get_user_skills_dir

        skills_dir = get_user_skills_dir(self.swe_root, user_id, agent_id)
        skill_dir = skills_dir / skill_name
        target = skill_dir / file_path

        # 安全检查：防止路径穿越
        try:
            target.resolve().relative_to(skill_dir.resolve())
        except ValueError:
            return None, "error"

        if not target.exists() or not target.is_file():
            return None, "error"

        # 判断文件类型
        ext = target.suffix.lower()
        if ext == ".md":
            file_type = "markdown"
        elif ext == ".json":
            file_type = "json"
        elif ext in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
            return None, "binary"
        elif ext == ".pdf":
            return None, "binary"
        else:
            file_type = "text"

        try:
            content = target.read_text(encoding="utf-8")
            return content, file_type
        except Exception:
            return None, "error"
```

- [ ] **Step 3: 添加 save_skill_file 方法**

```python
    def save_skill_file(
        self,
        user_id: str,
        skill_name: str,
        file_path: str,
        content: str,
        agent_id: str = "default",
    ) -> bool:
        """保存技能文件内容."""
        from .fs import get_user_skills_dir

        skills_dir = get_user_skills_dir(self.swe_root, user_id, agent_id)
        skill_dir = skills_dir / skill_name
        target = skill_dir / file_path

        # 安全检查：防止路径穿越
        try:
            target.resolve().relative_to(skill_dir.resolve())
        except ValueError:
            return False

        if not target.exists() or not target.is_file():
            return False

        try:
            target.write_text(content, encoding="utf-8")
            return True
        except Exception:
            return False
```

- [ ] **Step 4: 添加 delete_skill 方法**

```python
    def delete_skill(
        self,
        user_id: str,
        skill_name: str,
        agent_id: str = "default",
    ) -> bool:
        """删除用户技能."""
        import shutil
        from .fs import get_user_skills_dir

        skills_dir = get_user_skills_dir(self.swe_root, user_id, agent_id)
        skill_dir = skills_dir / skill_name

        if not skill_dir.exists():
            return False

        try:
            shutil.rmtree(skill_dir)
            return True
        except Exception:
            return False
```

- [ ] **Step 5: Commit**

```bash
git add market/src/market/marketplace/service.py
git commit -m "feat(market): add skill file operations (list/read/save/delete)"
```

---

### Task 3: 后端 API 端点

**Files:**
- Modify: `market/src/market/app/routers/skills_browse.py`

- [ ] **Step 1: 添加文件树 API**

在 `skills_browse.py` 中添加：

```python
from ...marketplace.schemas import (
    FileTreeNode,
    FileContentResponse,
    OperationResponse,
)


@router.get("/market/skills/mine/{skill_name}/files", response_model=list[FileTreeNode])
async def list_skill_files(
    skill_name: str,
    request: Request,
    x_source_id: Optional[str] = Header(default=None, alias="X-Source-Id"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    agent_id: str = "default",
):
    """获取技能文件树."""
    _require_source_id(x_source_id)
    if not x_user_id:
        raise HTTPException(status_code=400, detail="X-User-Id header is required")
    svc = request.app.state.marketplace
    return svc.list_skill_files(x_user_id, skill_name, agent_id)
```

- [ ] **Step 2: 添加文件读取 API**

```python
@router.get("/market/skills/mine/{skill_name}/files/{file_path:path}", response_model=FileContentResponse)
async def read_skill_file(
    skill_name: str,
    file_path: str,
    request: Request,
    x_source_id: Optional[str] = Header(default=None, alias="X-Source-Id"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    agent_id: str = "default",
):
    """读取技能文件内容."""
    _require_source_id(x_source_id)
    if not x_user_id:
        raise HTTPException(status_code=400, detail="X-User-Id header is required")
    svc = request.app.state.marketplace
    content, file_type = svc.read_skill_file(x_user_id, skill_name, file_path, agent_id)
    if content is None:
        if file_type == "binary":
            raise HTTPException(status_code=400, detail="Binary file not supported for preview")
        raise HTTPException(status_code=404, detail="File not found")
    return FileContentResponse(content=content, file_type=file_type)
```

- [ ] **Step 3: 添加文件保存 API**

```python
from fastapi import Body


@router.put("/market/skills/mine/{skill_name}/files/{file_path:path}", response_model=OperationResponse)
async def save_skill_file(
    skill_name: str,
    file_path: str,
    request: Request,
    content: str = Body(..., embed=True),
    x_source_id: Optional[str] = Header(default=None, alias="X-Source-Id"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    x_user_name: Optional[str] = Header(default=None, alias="X-User-Name"),
    agent_id: str = "default",
):
    """保存技能文件内容（仅我创建的技能支持）."""
    _require_source_id(x_source_id)
    if not x_user_id:
        raise HTTPException(status_code=400, detail="X-User-Id header is required")

    svc = request.app.state.marketplace
    # 检查是否是我创建的技能
    skills = await svc.get_my_skills(x_source_id, x_user_id, agent_id)
    skill = next((s for s in skills if s.skill_name == skill_name), None)
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    if skill.is_received:
        raise HTTPException(status_code=403, detail="Only created skills can be edited")

    ok = svc.save_skill_file(x_user_id, skill_name, file_path, content, agent_id)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to save file")
    return OperationResponse(success=True)
```

- [ ] **Step 4: 添加删除技能 API**

```python
@router.delete("/market/skills/mine/{skill_name}", response_model=OperationResponse)
async def delete_my_skill(
    skill_name: str,
    request: Request,
    x_source_id: Optional[str] = Header(default=None, alias="X-Source-Id"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    agent_id: str = "default",
):
    """删除技能."""
    _require_source_id(x_source_id)
    if not x_user_id:
        raise HTTPException(status_code=400, detail="X-User-Id header is required")

    svc = request.app.state.marketplace
    ok = svc.delete_skill(x_user_id, skill_name, agent_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Skill not found or delete failed")
    return OperationResponse(success=True)
```

- [ ] **Step 5: Commit**

```bash
git add market/src/market/app/routers/skills_browse.py
git commit -m "feat(market): add skill file and delete API endpoints"
```

---

### Task 4: 前端 API 模块扩展

**Files:**
- Modify: `console/src/api/modules/mySkills.ts`

- [ ] **Step 1: 扩展 mySkills API 模块**

重写 `console/src/api/modules/mySkills.ts`：

```typescript
import { request } from "../request";
import { buildAuthHeaders } from "../authHeaders";

export interface MySkill {
  skill_name: string;
  source: string;
  description: string;
  version: string | null;
  received_version: string | null;
  distributed_by: string | null;
  is_received: boolean;
  has_update: boolean;
  category?: string;
  creator_name?: string;
}

export interface FileTreeNode {
  name: string;
  type: "file" | "directory";
  path: string;
  children?: FileTreeNode[];
}

export interface FileContentResponse {
  content: string;
  file_type: string;
}

function mergeHeaders(extra?: Record<string, string>): RequestInit {
  const base = buildAuthHeaders();
  const merged: Record<string, string> = { ...base, ...(extra || {}) };
  return { headers: new Headers(merged) };
}

export const mySkillsApi = {
  getCreatedSkills: async (
    sourceId: string,
    userId: string
  ): Promise<MySkill[]> => {
    const opts = mergeHeaders({
      "X-Source-Id": sourceId,
      "X-User-Id": userId,
    });
    const all = await request<MySkill[]>("/market/skills/mine", opts);
    return all.filter((s) => !s.is_received);
  },

  getReceivedSkills: async (
    sourceId: string,
    userId: string
  ): Promise<MySkill[]> => {
    const opts = mergeHeaders({
      "X-Source-Id": sourceId,
      "X-User-Id": userId,
    });
    const all = await request<MySkill[]>("/market/skills/received", opts);
    return all.filter((s) => s.is_received);
  },

  listSkillFiles: async (
    sourceId: string,
    userId: string,
    userName: string,
    bbkId: string,
    skillName: string
  ): Promise<FileTreeNode[]> => {
    const opts = mergeHeaders({
      "X-Source-Id": sourceId,
      "X-User-Id": userId,
      "X-User-Name": encodeURIComponent(userName),
      "X-Bbk-Id": bbkId,
    });
    return request<FileTreeNode[]>(`/market/skills/mine/${skillName}/files`, opts);
  },

  readSkillFile: async (
    sourceId: string,
    userId: string,
    userName: string,
    bbkId: string,
    skillName: string,
    filePath: string
  ): Promise<FileContentResponse> => {
    const opts = mergeHeaders({
      "X-Source-Id": sourceId,
      "X-User-Id": userId,
      "X-User-Name": encodeURIComponent(userName),
      "X-Bbk-Id": bbkId,
    });
    return request<FileContentResponse>(
      `/market/skills/mine/${skillName}/files/${filePath}`,
      opts
    );
  },

  saveSkillFile: async (
    sourceId: string,
    userId: string,
    userName: string,
    bbkId: string,
    skillName: string,
    filePath: string,
    content: string
  ): Promise<void> => {
    const opts: RequestInit = {
      method: "PUT",
      headers: new Headers({
        "Content-Type": "application/json",
        "X-Source-Id": sourceId,
        "X-User-Id": userId,
        "X-User-Name": encodeURIComponent(userName),
        "X-Bbk-Id": bbkId,
      }),
      body: JSON.stringify({ content }),
    };
    await request<void>(`/market/skills/mine/${skillName}/files/${filePath}`, opts);
  },

  deleteSkill: async (
    sourceId: string,
    userId: string,
    userName: string,
    bbkId: string,
    skillName: string
  ): Promise<void> => {
    const opts: RequestInit = {
      method: "DELETE",
      headers: new Headers({
        "X-Source-Id": sourceId,
        "X-User-Id": userId,
        "X-User-Name": encodeURIComponent(userName),
        "X-Bbk-Id": bbkId,
      }),
    };
    await request<void>(`/market/skills/mine/${skillName}`, opts);
  },
};
```

- [ ] **Step 2: Commit**

```bash
git add console/src/api/modules/mySkills.ts
git commit -m "feat(console): add skill file and delete API methods"
```

---

### Task 5: 前端组件 - SkillFileTree

**Files:**
- Create: `console/src/pages/MySkills/components/SkillFileTree.tsx`

- [ ] **Step 1: 创建 SkillFileTree 组件**

```tsx
import { Typography } from "antd";
import { FolderOutlined, FileOutlined, DownOutlined, RightOutlined } from "@ant-design/icons";
import { FileTreeNode } from "../../api/modules/mySkills";

const { Text } = Typography;

interface Props {
  nodes: FileTreeNode[];
  level: number;
  skillName: string;
  expandedDirs: Set<string>;
  selectedFile: string | null;
  onToggleDir: (path: string) => void;
  onSelectFile: (path: string) => void;
}

export function SkillFileTree({
  nodes,
  level,
  skillName,
  expandedDirs,
  selectedFile,
  onToggleDir,
  onSelectFile,
}: Props) {
  return (
    <div>
      {nodes.map((node) => {
        const paddingLeft = 16 + level * 16;
        const isExpanded = expandedDirs.has(node.path);
        const isSelected = selectedFile === node.path;

        if (node.type === "directory") {
          return (
            <div key={node.path}>
              <div
                onClick={() => onToggleDir(node.path)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  padding: "6px 8px",
                  paddingLeft,
                  cursor: "pointer",
                  borderRadius: 4,
                  marginBottom: 2,
                  backgroundColor: isExpanded ? "#f5f5f5" : "transparent",
                }}
              >
                {isExpanded ? (
                  <DownOutlined style={{ fontSize: 10, marginRight: 6, color: "#8c8c8c" }} />
                ) : (
                  <RightOutlined style={{ fontSize: 10, marginRight: 6, color: "#8c8c8c" }} />
                )}
                <FolderOutlined style={{ fontSize: 14, marginRight: 6, color: "#faad14" }} />
                <Text style={{ fontSize: 13 }}>{node.name}</Text>
              </div>
              {isExpanded && node.children && (
                <SkillFileTree
                  nodes={node.children}
                  level={level + 1}
                  skillName={skillName}
                  expandedDirs={expandedDirs}
                  selectedFile={selectedFile}
                  onToggleDir={onToggleDir}
                  onSelectFile={onSelectFile}
                />
              )}
            </div>
          );
        }

        return (
          <div
            key={node.path}
            onClick={() => onSelectFile(node.path)}
            style={{
              display: "flex",
              alignItems: "center",
              padding: "6px 8px",
              paddingLeft: paddingLeft + 16,
              cursor: "pointer",
              borderRadius: 4,
              marginBottom: 2,
              backgroundColor: isSelected ? "#e6f4ff" : "transparent",
              border: isSelected ? "1px solid #1890ff" : "1px solid transparent",
            }}
          >
            <FileOutlined style={{ fontSize: 14, marginRight: 6, color: "#8c8c8c" }} />
            <Text style={{ fontSize: 13, color: isSelected ? "#1890ff" : "#262626" }}>
              {node.name}
            </Text>
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add console/src/pages/MySkills/components/SkillFileTree.tsx
git commit -m "feat(console): add SkillFileTree component"
```

---

### Task 6: 前端组件 - SkillDetail

**Files:**
- Create: `console/src/pages/MySkills/components/SkillDetail.tsx`

- [ ] **Step 1: 创建 SkillDetail 组件**

```tsx
import { Typography, Tag, Button, Spin, message } from "antd";
import { DeleteOutlined, CheckCircleOutlined, StopOutlined } from "@ant-design/icons";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { MySkill } from "../../api/modules/mySkills";
import { SkillFileEditor } from "./SkillFileEditor";

const { Title, Text } = Typography;

interface Props {
  skill: MySkill | null;
  fileContent: string | null;
  fileType: string | null;
  filePath: string | null;
  canEdit: boolean;
  disabled: boolean;
  onToggleEnabled: () => void;
  onDelete: () => void;
  onSaveContent: (content: string) => Promise<boolean>;
}

export function SkillDetail({
  skill,
  fileContent,
  fileType,
  filePath,
  canEdit,
  disabled,
  onToggleEnabled,
  onDelete,
  onSaveContent,
}: Props) {
  const [editing, setEditing] = useState(false);
  const [draftContent, setDraftContent] = useState("");
  const [saving, setSaving] = useState(false);

  if (!skill) {
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", padding: 32, textAlign: "center" }}>
        <Title level={5} style={{ margin: "0 0 8px 0" }}>技能详情</Title>
        <Text type="secondary">选择左侧技能查看详情</Text>
      </div>
    );
  }

  const handleStartEdit = () => {
    setDraftContent(fileContent || "");
    setEditing(true);
  };

  const handleCancelEdit = () => {
    setEditing(false);
    setDraftContent("");
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const ok = await onSaveContent(draftContent);
      if (ok) {
        setEditing(false);
        message.success("保存成功");
      }
    } finally {
      setSaving(false);
    }
  };

  const isLoading = filePath && fileContent === null;

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      {/* Header */}
      <div style={{ padding: 16, borderBottom: "1px solid #f0f0f0" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
          <Title level={4} style={{ margin: 0 }}>
            {skill.skill_name}
          </Title>
          <div style={{ display: "flex", gap: 8 }}>
            {!editing && canEdit && fileContent !== null && (
              <Button size="small" onClick={handleStartEdit}>
                编辑
              </Button>
            )}
            <Button
              size="small"
              icon={disabled ? <CheckCircleOutlined /> : <StopOutlined />}
              onClick={onToggleEnabled}
            >
              {disabled ? "启用" : "禁用"}
            </Button>
            <Button
              size="small"
              danger
              icon={<DeleteOutlined />}
              onClick={onDelete}
            >
              删除
            </Button>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {skill.version && <Tag color="blue">v{skill.version}</Tag>}
          {skill.source === "customized" && <Tag color="green">自定义</Tag>}
          {skill.is_received && <Tag color="orange">接收的</Tag>}
          {disabled && <Tag color="red">已禁用</Tag>}
        </div>
      </div>

      {/* Description */}
      <div style={{ padding: "12px 16px", borderBottom: "1px solid #f0f0f0" }}>
        <Text type="secondary">{skill.description || "暂无描述"}</Text>
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflow: "auto", padding: 16 }}>
        {isLoading ? (
          <Spin />
        ) : editing ? (
          <SkillFileEditor
            content={draftContent}
            fileType={fileType || "text"}
            onChange={setDraftContent}
            onSave={handleSave}
            onCancel={handleCancelEdit}
            saving={saving}
          />
        ) : fileContent === null ? (
          <Text type="secondary">选择文件查看内容</Text>
        ) : fileType === "markdown" ? (
          <div style={{ background: "#fafafa", padding: 16, borderRadius: 8 }}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{fileContent}</ReactMarkdown>
          </div>
        ) : fileType === "json" ? (
          <pre style={{ background: "#fafafa", padding: 16, borderRadius: 8, overflow: "auto", fontSize: 12 }}>
            {JSON.stringify(JSON.parse(fileContent), null, 2)}
          </pre>
        ) : (
          <pre style={{ background: "#fafafa", padding: 16, borderRadius: 8, overflow: "auto", fontSize: 12 }}>
            {fileContent}
          </pre>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add console/src/pages/MySkills/components/SkillDetail.tsx
git commit -m "feat(console): add SkillDetail component"
```

---

### Task 7: 前端组件 - SkillFileEditor

**Files:**
- Create: `console/src/pages/MySkills/components/SkillFileEditor.tsx`

- [ ] **Step 1: 创建 SkillFileEditor 组件**

```tsx
import { Input, Button, Space, message } from "antd";
import { SaveOutlined, CloseOutlined } from "@ant-design/icons";

const { TextArea } = Input;

interface Props {
  content: string;
  fileType: string;
  onChange: (content: string) => void;
  onSave: () => void;
  onCancel: () => void;
  saving: boolean;
}

export function SkillFileEditor({
  content,
  fileType,
  onChange,
  onSave,
  onCancel,
  saving,
}: Props) {
  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <div style={{ marginBottom: 12, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontSize: 12, color: "#8c8c8c" }}>
          编辑模式 - {fileType === "markdown" ? "Markdown" : fileType === "json" ? "JSON" : "文本"}
        </span>
        <Space>
          <Button size="small" icon={<CloseOutlined />} onClick={onCancel} disabled={saving}>
            取消
          </Button>
          <Button size="small" type="primary" icon={<SaveOutlined />} onClick={onSave} loading={saving}>
            保存
          </Button>
        </Space>
      </div>
      <TextArea
        value={content}
        onChange={(e) => onChange(e.target.value)}
        style={{ flex: 1, fontFamily: "monospace", fontSize: 13 }}
        placeholder="输入内容..."
      />
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add console/src/pages/MySkills/components/SkillFileEditor.tsx
git commit -m "feat(console): add SkillFileEditor component"
```

---

### Task 8: 前端组件 - SkillItem

**Files:**
- Create: `console/src/pages/MySkills/components/SkillItem.tsx`

- [ ] **Step 1: 创建 SkillItem 组件**

```tsx
import { Typography, Tag } from "antd";
import { DownOutlined, RightOutlined } from "@ant-design/icons";
import { useState, useEffect } from "react";
import { MySkill, FileTreeNode, mySkillsApi } from "../../api/modules/mySkills";
import { SkillFileTree } from "./SkillFileTree";

const { Text } = Typography;

interface Props {
  skill: MySkill;
  expanded: boolean;
  selected: boolean;
  disabled: boolean;
  sourceId: string;
  userId: string;
  userName: string;
  bbkId: string;
  selectedFile: string | null;
  expandedDirs: Set<string>;
  onToggle: () => void;
  onSelectFile: (path: string) => void;
  onToggleDir: (path: string) => void;
}

export function SkillItem({
  skill,
  expanded,
  selected,
  disabled,
  sourceId,
  userId,
  userName,
  bbkId,
  selectedFile,
  expandedDirs,
  onToggle,
  onSelectFile,
  onToggleDir,
}: Props) {
  const [files, setFiles] = useState<FileTreeNode[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (expanded && files.length === 0) {
      setLoading(true);
      mySkillsApi.listSkillFiles(sourceId, userId, userName, bbkId, skill.skill_name)
        .then(setFiles)
        .catch(console.error)
        .finally(() => setLoading(false));
    }
  }, [expanded, skill.skill_name, sourceId, userId, userName, bbkId, files.length]);

  return (
    <div
      style={{
        borderRadius: 8,
        border: "1px solid #f0f0f0",
        marginBottom: 8,
        overflow: "hidden",
        backgroundColor: selected ? "#e6f4ff" : "#fff",
      }}
    >
      <div
        onClick={onToggle}
        style={{
          display: "flex",
          alignItems: "center",
          padding: "10px 12px",
          cursor: "pointer",
          borderBottom: expanded ? "1px solid #f0f0f0" : "none",
        }}
      >
        {expanded ? (
          <DownOutlined style={{ fontSize: 10, marginRight: 8, color: "#8c8c8c" }} />
        ) : (
          <RightOutlined style={{ fontSize: 10, marginRight: 8, color: "#8c8c8c" }} />
        )}
        <Text
          strong={selected}
          style={{
            flex: 1,
            textDecoration: disabled ? "line-through" : "none",
            color: disabled ? "#8c8c8c" : "#262626",
          }}
        >
          {skill.skill_name}
        </Text>
        {skill.version && <Tag style={{ marginLeft: 4 }}>v{skill.version}</Tag>}
        {skill.is_received && <Tag color="orange">接收的</Tag>}
        {skill.has_update && <Tag color="red">有更新</Tag>}
      </div>
      {expanded && (
        <div style={{ padding: "8px 0" }}>
          {loading ? (
            <Text type="secondary" style={{ padding: "0 16px" }}>加载中...</Text>
          ) : files.length === 0 ? (
            <Text type="secondary" style={{ padding: "0 16px" }}>没有文件</Text>
          ) : (
            <SkillFileTree
              nodes={files}
              level={0}
              skillName={skill.skill_name}
              expandedDirs={expandedDirs}
              selectedFile={selectedFile}
              onToggleDir={onToggleDir}
              onSelectFile={onSelectFile}
            />
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add console/src/pages/MySkills/components/SkillItem.tsx
git commit -m "feat(console): add SkillItem component with file tree"
```

---

### Task 9: 重构 MySkills 主页面

**Files:**
- Modify: `console/src/pages/MySkills/index.tsx`

- [ ] **Step 1: 重写主页面**

```tsx
import { useEffect, useState, useCallback } from "react";
import { Typography, Input, Button, Space, Spin, message, Popconfirm } from "antd";
import { SearchOutlined, UploadOutlined, ShopOutlined, DeleteOutlined } from "@ant-design/icons";
import { useMySkills } from "./useMySkills";
import { useIframeStore } from "../../stores/iframeStore";
import { getUserId } from "../../utils/identity";
import { DEFAULT_SOURCE_ID } from "../../constants/identity";
import { MySkill, mySkillsApi } from "../../api/modules/mySkills";
import { SkillItem } from "./components/SkillItem";
import { SkillDetail } from "./components/SkillDetail";
import { marketApi } from "../../api/modules/market";

const { Title, Text } = Typography;

const DISABLED_SKILLS_KEY = "copaw_disabled_skills";

function getDisabledSkills(): Set<string> {
  try {
    const raw = localStorage.getItem(DISABLED_SKILLS_KEY);
    return raw ? new Set(JSON.parse(raw)) : new Set();
  } catch {
    return new Set();
  }
}

function setDisabledSkills(set: Set<string>) {
  localStorage.setItem(DISABLED_SKILLS_KEY, JSON.stringify([...set]));
}

export default function MySkillsPage() {
  const sourceId = useIframeStore((state) => state.source) || DEFAULT_SOURCE_ID;
  const bbkId = useIframeStore((state) => state.bbk) || "100";
  const isManager = useIframeStore((state) => state.manager) || false;
  const userId = getUserId();
  const userName = useIframeStore((state) => state.clawName) || userId;
  const { createdSkills, receivedSkills, loading, refresh } = useMySkills(sourceId, userId);

  const [searchText, setSearchText] = useState("");
  const [expandedSkills, setExpandedSkills] = useState<Set<string>>(new Set());
  const [expandedDirs, setExpandedDirs] = useState<Set<string>>(new Set());
  const [selectedSkill, setSelectedSkill] = useState<MySkill | null>(null);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState<string | null>(null);
  const [fileType, setFileType] = useState<string | null>(null);
  const [disabledSkills, setDisabledSkillsState] = useState<Set<string>>(getDisabledSkills);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const toggleSkill = useCallback((skill: MySkill) => {
    setExpandedSkills((prev) => {
      const next = new Set(prev);
      if (next.has(skill.skill_name)) {
        next.delete(skill.skill_name);
      } else {
        next.clear();
        next.add(skill.skill_name);
      }
      return next;
    });
    setSelectedSkill(skill);
    setSelectedFile(null);
    setFileContent(null);
  }, []);

  const toggleDir = useCallback((path: string) => {
    setExpandedDirs((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }, []);

  const selectFile = useCallback(async (skill: MySkill, filePath: string) => {
    setSelectedFile(filePath);
    setFileContent(null);
    try {
      const res = await mySkillsApi.readSkillFile(
        sourceId, userId, userName, bbkId, skill.skill_name, filePath
      );
      setFileContent(res.content);
      setFileType(res.file_type);
    } catch (err) {
      message.error("加载文件失败");
      setFileContent("");
    }
  }, [sourceId, userId, userName, bbkId]);

  const toggleDisabled = useCallback((skillName: string) => {
    setDisabledSkillsState((prev) => {
      const next = new Set(prev);
      if (next.has(skillName)) next.delete(skillName);
      else next.add(skillName);
      setDisabledSkills(next);
      return next;
    });
  }, []);

  const handleDelete = useCallback(async (skill: MySkill) => {
    try {
      await mySkillsApi.deleteSkill(sourceId, userId, userName, bbkId, skill.skill_name);
      message.success("删除成功");
      refresh();
      setSelectedSkill(null);
      setSelectedFile(null);
      setFileContent(null);
    } catch (err) {
      message.error("删除失败");
    }
  }, [sourceId, userId, userName, bbkId, refresh]);

  const saveContent = useCallback(async (content: string): Promise<boolean> => {
    if (!selectedSkill || !selectedFile) return false;
    try {
      await mySkillsApi.saveSkillFile(
        sourceId, userId, userName, bbkId, selectedSkill.skill_name, selectedFile, content
      );
      setFileContent(content);
      return true;
    } catch (err) {
      message.error("保存失败");
      return false;
    }
  }, [selectedSkill, selectedFile, sourceId, userId, userName, bbkId]);

  const filterSkills = (skills: MySkill[]) => {
    const q = searchText.trim().toLowerCase();
    if (!q) return skills;
    return skills.filter((s) =>
      s.skill_name.toLowerCase().includes(q) ||
      (s.description?.toLowerCase().includes(q) ?? false)
    );
  };

  const filteredCreated = filterSkills(createdSkills);
  const filteredReceived = filterSkills(receivedSkills);

  const allSkills = [...createdSkills, ...receivedSkills];
  const currentSkill = selectedSkill;
  const currentDisabled = currentSkill ? disabledSkills.has(currentSkill.skill_name) : false;
  const canEdit = currentSkill ? !currentSkill.is_received : false;

  return (
    <div style={{ display: "flex", height: "100%", backgroundColor: "#fff" }}>
      {/* Left sidebar */}
      <div style={{ width: 320, flexShrink: 0, borderRight: "1px solid #f0f0f0", display: "flex", flexDirection: "column" }}>
        <div style={{ padding: 16, borderBottom: "1px solid #f0f0f0" }}>
          <Input
            placeholder="搜索技能"
            prefix={<SearchOutlined />}
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            allowClear
            style={{ marginBottom: 8 }}
          />
          <div style={{ display: "flex", gap: 8 }}>
            <Button icon={<UploadOutlined />} style={{ flex: 1 }}>
              上传技能
            </Button>
            <Button icon={<ShopOutlined />} style={{ flex: 1 }}>
              去应用市场
            </Button>
          </div>
        </div>
        <div style={{ flex: 1, overflow: "auto", padding: 12 }}>
          {loading ? (
            <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: 100 }}>
              <Spin />
            </div>
          ) : (
            <>
              <div style={{ marginBottom: 16 }}>
                <Text type="secondary" style={{ fontSize: 12, fontWeight: 500 }}>我创建的 ({filteredCreated.length})</Text>
              </div>
              {filteredCreated.map((skill) => (
                <SkillItem
                  key={skill.skill_name}
                  skill={skill}
                  expanded={expandedSkills.has(skill.skill_name)}
                  selected={selectedSkill?.skill_name === skill.skill_name}
                  disabled={disabledSkills.has(skill.skill_name)}
                  sourceId={sourceId}
                  userId={userId}
                  userName={userName}
                  bbkId={bbkId}
                  selectedFile={selectedFile}
                  expandedDirs={expandedDirs}
                  onToggle={() => toggleSkill(skill)}
                  onSelectFile={(path) => selectFile(skill, path)}
                  onToggleDir={toggleDir}
                />
              ))}

              <div style={{ margin: "16px 0 8px" }}>
                <Text type="secondary" style={{ fontSize: 12, fontWeight: 500 }}>我接收的 ({filteredReceived.length})</Text>
              </div>
              {filteredReceived.map((skill) => (
                <SkillItem
                  key={skill.skill_name}
                  skill={skill}
                  expanded={expandedSkills.has(skill.skill_name)}
                  selected={selectedSkill?.skill_name === skill.skill_name}
                  disabled={disabledSkills.has(skill.skill_name)}
                  sourceId={sourceId}
                  userId={userId}
                  userName={userName}
                  bbkId={bbkId}
                  selectedFile={selectedFile}
                  expandedDirs={expandedDirs}
                  onToggle={() => toggleSkill(skill)}
                  onSelectFile={(path) => selectFile(skill, path)}
                  onToggleDir={toggleDir}
                />
              ))}
            </>
          )}
        </div>
      </div>

      {/* Right detail panel */}
      <div style={{ flex: 1, overflow: "hidden" }}>
        <SkillDetail
          skill={currentSkill}
          fileContent={fileContent}
          fileType={fileType}
          filePath={selectedFile}
          canEdit={canEdit}
          disabled={currentDisabled}
          onToggleEnabled={() => currentSkill && toggleDisabled(currentSkill.skill_name)}
          onDelete={() => currentSkill && handleDelete(currentSkill)}
          onSaveContent={saveContent}
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 删除不再需要的旧组件**

```bash
rm console/src/pages/MySkills/CreatedSkills.tsx
rm console/src/pages/MySkills/ReceivedSkills.tsx
```

- [ ] **Step 3: Commit**

```bash
git add console/src/pages/MySkills/
git commit -m "feat(console): rewrite MySkills page with file tree and detail panel"
```

---

## 自检

**Spec 覆盖：**
- [x] 树形文件浏览 — Task 5 SkillFileTree + Task 8 SkillItem
- [x] 文件内容预览 — Task 6 SkillDetail
- [x] 编辑文件（我创建的）— Task 7 SkillFileEditor + Task 6
- [x] 删除技能 — Task 3 API + Task 9 页面
- [x] 启用/禁用（前端 localStorage）— Task 9
- [x] 后端文件操作 API — Task 2, Task 3
- [x] 前端 API 模块 — Task 4

**占位符扫描：** 无 TBD/TODO，所有代码完整。

**类型一致性：**
- FileTreeNode 在后端和前端定义一致
- MySkill 接口与 API 响应匹配
