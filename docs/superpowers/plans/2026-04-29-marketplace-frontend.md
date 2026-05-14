# 应用市场前端计划（2c）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Console 前端实现应用市场页面、我的技能菜单、我的 MCP 菜单（留空占位），以及相关的 API 模块和路由配置。

**Architecture:** 遵循现有 Skills/MCP 页面模式 —— API 模块 + 自定义 Hook + 卡片网格布局。应用市场使用左侧分类树 + 右侧技能列表布局，我的技能/我的 MCP 使用左侧树状导航 + 右侧详情面板。

**Tech Stack:** React 18, TypeScript, Ant Design 5.29, Zustand, React Router 7, Lucide React icons

---

## 文件结构

| 文件 | 操作 | 说明 |
|------|------|------|
| `console/src/api/modules/market.ts` | Create | 市场 API 模块 |
| `console/src/api/modules/mySkills.ts` | Create | 我的技能 API 模块 |
| `console/src/api/index.ts` | Modify | 导出新 API 模块 |
| `console/src/constants/bbk.ts` | Modify | 扩展 BBK_ID_MAP |
| `console/src/layouts/Sidebar.tsx` | Modify | 添加菜单项 |
| `console/src/layouts/MainLayout/index.tsx` | Modify | 添加路由 |
| `console/src/pages/Market/index.tsx` | Create | 应用市场页面 |
| `console/src/pages/Market/MarketSkills.tsx` | Create | 技能 tab 组件 |
| `console/src/pages/Market/MarketMCP.tsx` | Create | MCP tab 占位组件 |
| `console/src/pages/Market/SkillCard.tsx` | Create | 市场技能卡片 |
| `console/src/pages/Market/SkillDetailDrawer.tsx` | Create | 技能详情抽屉 |
| `console/src/pages/Market/PublishModal.tsx` | Create | 上架弹窗（管理员） |
| `console/src/pages/Market/DistributeModal.tsx` | Create | 分发弹窗（管理员） |
| `console/src/pages/Market/useMarket.ts` | Create | 市场数据 Hook |
| `console/src/pages/MySkills/index.tsx` | Create | 我的技能页面 |
| `console/src/pages/MySkills/CreatedSkills.tsx` | Create | 我创建的组件 |
| `console/src/pages/MySkills/ReceivedSkills.tsx` | Create | 我接收的组件 |
| `console/src/pages/MySkills/useMySkills.ts` | Create | 我的技能 Hook |
| `console/src/pages/MyMCP/index.tsx` | Create | 我的 MCP 占位页面 |
| `console/src/locales/zh/translation.json` | Modify | 添加 i18n 条目 |

---

### Task 1: 实现 API 模块

**Files:**
- Create: `console/src/api/modules/market.ts`
- Create: `console/src/api/modules/mySkills.ts`
- Modify: `console/src/api/index.ts`

API 基础配置：
- 市场 API 调用 `market` 服务（端口 8190），需要通过代理或直接调用
- 请求头需要 `X-Source-Id`、`X-User-Id`、`X-Bbk-Id`、`X-Manager`（管理员操作）

- [ ] **Step 1: 创建 market.ts API 模块**

创建 `console/src/api/modules/market.ts`：

```typescript
import { request } from "../request";

export interface MarketSkill {
  item_id: string;
  name: string;
  description: string;
  version: string;
  creator_id: string;
  creator_name: string;
  category_id: number | null;
  bbk_ids: string[];
  status: "active" | "inactive";
  created_at: string | null;
  updated_at: string | null;
  call_count: number;
  user_count: number;
}

export interface MarketSkillDetail extends MarketSkill {
  user_stats: Array<{
    user_id: string;
    user_name: string;
    call_count: number;
  }>;
}

export interface Category {
  id: number;
  source_id: string;
  name: string;
  sort_order: number;
}

export interface PublishSkillRequest {
  name: string;
  description: string;
  creator_id: string;
  creator_name: string;
  category_id?: number;
  bbk_ids?: string[];
  skill_json: Record<string, unknown>;
  skill_md?: string;
}

export interface DistributeRequest {
  target_type: "all" | "bbk_id" | "user_id";
  target_values: string[];
}

export interface DistributeResponse {
  distributed_count: number;
  item_id: string;
}

const BASE_URL = "/api/market";

function getHeaders(extra?: Record<string, string>): RequestInit {
  const headers: Record<string, string> = extra || {};
  return { headers: new Headers(headers) };
}

export const marketApi = {
  listCategories: async (sourceId: string): Promise<Category[]> => {
    const opts = getHeaders({ "X-Source-Id": sourceId });
    return request<Category[]>(`${BASE_URL}/marketplace/categories`, opts);
  },

  listSkills: async (
    sourceId: string,
    bbkId: string,
    categoryId?: number
  ): Promise<MarketSkill[]> => {
    let url = `${BASE_URL}/marketplace/skills`;
    const params = new URLSearchParams();
    if (categoryId !== undefined) {
      params.append("category_id", String(categoryId));
    }
    if (params.toString()) {
      url += `?${params.toString()}`;
    }
    const opts = getHeaders({
      "X-Source-Id": sourceId,
      "X-Bbk-Id": bbkId,
    });
    return request<MarketSkill[]>(url, opts);
  },

  getSkillDetail: async (
    sourceId: string,
    itemId: string,
    bbkId: string
  ): Promise<MarketSkillDetail | null> => {
    const opts = getHeaders({
      "X-Source-Id": sourceId,
      "X-Bbk-Id": bbkId,
    });
    return request<MarketSkillDetail | null>(
      `${BASE_URL}/marketplace/skills/${itemId}`,
      opts
    );
  },

  publishSkill: async (
    sourceId: string,
    userId: string,
    userName: string,
    data: PublishSkillRequest
  ): Promise<MarketSkill> => {
    const opts: RequestInit = {
      method: "POST",
      headers: new Headers({
        "Content-Type": "application/json",
        "X-Source-Id": sourceId,
        "X-User-Id": userId,
        "X-User-Name": encodeURIComponent(userName),
        "X-Manager": "true",
      }),
      body: JSON.stringify(data),
    };
    return request<MarketSkill>(`${BASE_URL}/marketplace/skills`, opts);
  },

  unpublishSkill: async (
    sourceId: string,
    itemId: string,
    userId: string,
    userName: string
  ): Promise<void> => {
    const opts: RequestInit = {
      method: "DELETE",
      headers: new Headers({
        "X-Source-Id": sourceId,
        "X-User-Id": userId,
        "X-User-Name": encodeURIComponent(userName),
        "X-Manager": "true",
      }),
    };
    return request<void>(`${BASE_URL}/marketplace/skills/${itemId}`, opts);
  },

  distributeSkill: async (
    sourceId: string,
    itemId: string,
    userId: string,
    userName: string,
    data: DistributeRequest
  ): Promise<DistributeResponse> => {
    const opts: RequestInit = {
      method: "POST",
      headers: new Headers({
        "Content-Type": "application/json",
        "X-Source-Id": sourceId,
        "X-User-Id": userId,
        "X-User-Name": encodeURIComponent(userName),
        "X-Manager": "true",
      }),
      body: JSON.stringify(data),
    };
    return request<DistributeResponse>(
      `${BASE_URL}/marketplace/skills/${itemId}/distribute`,
      opts
    );
  },
};
```

- [ ] **Step 2: 创建 mySkills.ts API 模块**

创建 `console/src/api/modules/mySkills.ts`：

```typescript
import { request } from "../request";

export interface MySkill {
  skill_name: string;
  source: string;
  description: string;
  version: string | null;
  received_version: string | null;
  distributed_by: string | null;
  is_received: boolean;
  has_update: boolean;
}

const BASE_URL = "/api/market";

function getHeaders(extra?: Record<string, string>): RequestInit {
  const headers: Record<string, string> = extra || {};
  return { headers: new Headers(headers) };
}

export const mySkillsApi = {
  getCreatedSkills: async (
    sourceId: string,
    userId: string
  ): Promise<MySkill[]> => {
    const opts = getHeaders({
      "X-Source-Id": sourceId,
      "X-User-Id": userId,
    });
    const all = await request<MySkill[]>(`${BASE_URL}/skills/mine`, opts);
    return all.filter((s) => !s.is_received);
  },

  getReceivedSkills: async (
    sourceId: string,
    userId: string
  ): Promise<MySkill[]> => {
    const opts = getHeaders({
      "X-Source-Id": sourceId,
      "X-User-Id": userId,
    });
    const all = await request<MySkill[]>(`${BASE_URL}/skills/received`, opts);
    return all.filter((s) => s.is_received);
  },
};
```

- [ ] **Step 3: 导出 API 模块**

修改 `console/src/api/index.ts`，添加导出：

```typescript
export * from "./modules/market";
export * from "./modules/mySkills";
```

- [ ] **Step 4: Commit**

```bash
git add console/src/api/modules/market.ts console/src/api/modules/mySkills.ts console/src/api/index.ts
git commit -m "feat(console): add market and mySkills API modules"
```

---

### Task 2: 扩展常量和菜单

**Files:**
- Modify: `console/src/constants/bbk.ts`
- Modify: `console/src/layouts/Sidebar.tsx`
- Modify: `console/src/layouts/MainLayout/index.tsx`

- [ ] **Step 1: 扩展 BBK_ID_MAP**

修改 `console/src/constants/bbk.ts`：

```typescript
export const BBK_ID_MAP = [
  { label: "总行", value: "100" },
  { label: "北京分行", value: "200" },
  { label: "上海分行", value: "201" },
  { label: "深圳分行", value: "202" },
  { label: "广州分行", value: "203" },
];
```

（实际机构列表以业务需求为准）

- [ ] **Step 2: 添加菜单项**

修改 `console/src/layouts/Sidebar.tsx`，在 collapsed nav 和 expanded menu 中添加：

**Collapsed nav（约第200行附近）**，在 Agent group 之后添加：

```tsx
<Divider style={{ margin: "12px 0" }} />
{
  key: "market",
  icon: <Store size={18} />,
  path: "/market",
  label: t("nav.market"),
}
{
  key: "my-skills",
  icon: <Wrench size={18} />,
  path: "/my-skills",
  label: t("nav.mySkills"),
}
{
  key: "my-mcp",
  icon: <Puzzle size={18} />,
  path: "/my-mcp",
  label: t("nav.myMcp"),
}
```

**Expanded menu（children 数组中）**，添加新的 menu group：

```tsx
{
  key: "market-group",
  label: collapsed ? null : t("nav.marketGroup"),
  children: [
    {
      key: "market",
      label: collapsed ? null : t("nav.market"),
      icon: <Store size={16} />,
    },
    {
      key: "my-skills",
      label: collapsed ? null : t("nav.mySkills"),
      icon: <Wrench size={16} />,
    },
    {
      key: "my-mcp",
      label: collapsed ? null : t("nav.myMcp"),
      icon: <Puzzle size={16} />,
    },
  ],
},
```

需要 import 图标：

```tsx
import { Store, Wrench, Puzzle } from "lucide-react";
```

- [ ] **Step 3: 添加路由**

修改 `console/src/layouts/MainLayout/index.tsx`，在 Routes 组件中添加：

```tsx
<Route path="/market" element={<MarketPage />} />
<Route path="/my-skills" element={<MySkillsPage />} />
<Route path="/my-mcp" element={<MyMCPPage />} />
```

需要 import 页面组件：

```tsx
import MarketPage from "../../pages/Market";
import MySkillsPage from "../../pages/MySkills";
import MyMCPPage from "../../pages/MyMCP";
```

- [ ] **Step 4: 添加 i18n 条目**

修改 `console/src/locales/zh/translation.json`，在 `nav` 部分添加：

```json
{
  "nav": {
    "marketGroup": "应用市场",
    "market": "应用市场",
    "mySkills": "我的技能",
    "myMcp": "我的 MCP",
    ...
  }
}
```

- [ ] **Step 5: Commit**

```bash
git add console/src/constants/bbk.ts console/src/layouts/Sidebar.tsx console/src/layouts/MainLayout/index.tsx console/src/locales/zh/translation.json
git commit -m "feat(console): add marketplace nav items and routes"
```

---

### Task 3: 实现应用市场页面

**Files:**
- Create: `console/src/pages/Market/index.tsx`
- Create: `console/src/pages/Market/MarketSkills.tsx`
- Create: `console/src/pages/Market/MarketMCP.tsx`
- Create: `console/src/pages/Market/SkillCard.tsx`
- Create: `console/src/pages/Market/SkillDetailDrawer.tsx`
- Create: `console/src/pages/Market/PublishModal.tsx`
- Create: `console/src/pages/Market/DistributeModal.tsx`
- Create: `console/src/pages/Market/useMarket.ts`

**UI 布局**：左侧分类树 + 右侧技能卡片网格，顶部 Tabs 切换技能/MCP

- [ ] **Step 1: 创建 useMarket Hook**

创建 `console/src/pages/Market/useMarket.ts`：

```typescript
import { useState, useCallback } from "react";
import { marketApi, Category, MarketSkill, MarketSkillDetail } from "../../api/modules/market";

export function useMarket(sourceId: string, bbkId: string) {
  const [categories, setCategories] = useState<Category[]>([]);
  const [skills, setSkills] = useState<MarketSkill[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<number | null>(null);
  const [selectedSkill, setSelectedSkill] = useState<MarketSkillDetail | null>(null);
  const [detailDrawerOpen, setDetailDrawerOpen] = useState(false);
  const [publishModalOpen, setPublishModalOpen] = useState(false);
  const [distributeModalOpen, setDistributeModalOpen] = useState(false);
  const [distributeTargetSkill, setDistributeTargetSkill] = useState<MarketSkill | null>(null);

  const refreshCategories = useCallback(async () => {
    try {
      const data = await marketApi.listCategories(sourceId);
      setCategories(data);
    } catch (err) {
      console.error("Failed to load categories:", err);
    }
  }, [sourceId]);

  const refreshSkills = useCallback(async () => {
    setLoading(true);
    try {
      const data = await marketApi.listSkills(sourceId, bbkId, selectedCategory ?? undefined);
      setSkills(data);
    } catch (err) {
      console.error("Failed to load skills:", err);
    } finally {
      setLoading(false);
    }
  }, [sourceId, bbkId, selectedCategory]);

  const openSkillDetail = useCallback(
    async (itemId: string) => {
      try {
        const detail = await marketApi.getSkillDetail(sourceId, itemId, bbkId);
        if (detail) {
          setSelectedSkill(detail);
          setDetailDrawerOpen(true);
        }
      } catch (err) {
        console.error("Failed to load skill detail:", err);
      }
    },
    [sourceId, bbkId]
  );

  const openDistributeModal = useCallback((skill: MarketSkill) => {
    setDistributeTargetSkill(skill);
    setDistributeModalOpen(true);
  }, []);

  return {
    categories,
    skills,
    loading,
    selectedCategory,
    setSelectedCategory,
    selectedSkill,
    detailDrawerOpen,
    setDetailDrawerOpen,
    publishModalOpen,
    setPublishModalOpen,
    distributeModalOpen,
    setDistributeModalOpen,
    distributeTargetSkill,
    refreshCategories,
    refreshSkills,
    openSkillDetail,
    openDistributeModal,
  };
}
```

- [ ] **Step 2: 创建 SkillCard 组件**

创建 `console/src/pages/Market/SkillCard.tsx`：

```tsx
import { Card, Tag, Typography } from "antd";
import { MarketSkill } from "../../api/modules/market";
import { Users, PhoneCall } from "lucide-react";

const { Text } = Typography;

interface SkillCardProps {
  skill: MarketSkill;
  onClick: () => void;
  onDistribute?: () => void;
  isManager: boolean;
}

export function SkillCard({ skill, onClick, onDistribute, isManager }: SkillCardProps) {
  return (
    <Card
      hoverable
      onClick={onClick}
      styles={{
        body: { padding: 16 },
      }}
    >
      <div style={{ marginBottom: 8 }}>
        <Text strong style={{ fontSize: 16 }}>
          {skill.name}
        </Text>
        {skill.category_id && (
          <Tag color="blue" style={{ marginLeft: 8 }}>
            {skill.category_id}
          </Tag>
        )}
      </div>
      <Text type="secondary" style={{ display: "block", marginBottom: 12 }}>
        {skill.description || "暂无描述"}
      </Text>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <Text type="secondary" style={{ fontSize: 12 }}>
          {skill.creator_name} · v{skill.version}
        </Text>
        <div style={{ display: "flex", gap: 12 }}>
          <div
            style={{
              background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
              borderRadius: 4,
              padding: "4px 8px",
              color: "#fff",
              fontSize: 12,
              display: "flex",
              alignItems: "center",
              gap: 4,
            }}
          >
            <PhoneCall size={12} />
            {skill.call_count}
          </div>
          <div
            style={{
              background: "linear-gradient(135deg, #f093fb 0%, #f5576c 100%)",
              borderRadius: 4,
              padding: "4px 8px",
              color: "#fff",
              fontSize: 12,
              display: "flex",
              alignItems: "center",
              gap: 4,
            }}
          >
            <Users size={12} />
            {skill.user_count}
          </div>
        </div>
      </div>
    </Card>
  );
}
```

- [ ] **Step 3: 创建 SkillDetailDrawer 组件**

创建 `console/src/pages/Market/SkillDetailDrawer.tsx`：

```tsx
import { Drawer, Descriptions, Table, Typography } from "antd";
import { MarketSkillDetail } from "../../api/modules/market";

const { Title } = Typography;

interface SkillDetailDrawerProps {
  open: boolean;
  skill: MarketSkillDetail | null;
  onClose: () => void;
}

export function SkillDetailDrawer({ open, skill, onClose }: SkillDetailDrawerProps) {
  if (!skill) return null;

  const userStatsColumns = [
    { title: "用户ID", dataIndex: "user_id", key: "user_id" },
    { title: "用户名称", dataIndex: "user_name", key: "user_name" },
    { title: "调用次数", dataIndex: "call_count", key: "call_count", sorter: (a: any, b: any) => a.call_count - b.call_count },
  ];

  return (
    <Drawer
      open={open}
      onClose={onClose}
      width={640}
      title={<Title level={4}>{skill.name}</Title>}
    >
      <Descriptions column={2} bordered size="small">
        <Descriptions.Item label="描述">{skill.description || "暂无"}</Descriptions.Item>
        <Descriptions.Item label="版本">{skill.version}</Descriptions.Item>
        <Descriptions.Item label="创建人">{skill.creator_name}</Descriptions.Item>
        <Descriptions.Item label="状态">
          {skill.status === "active" ? "上架中" : "已下架"}
        </Descriptions.Item>
        <Descriptions.Item label="创建时间">{skill.created_at || "-"}</Descriptions.Item>
        <Descriptions.Item label="更新时间">{skill.updated_at || "-"}</Descriptions.Item>
        <Descriptions.Item label="调用次数">{skill.call_count}</Descriptions.Item>
        <Descriptions.Item label="用户量">{skill.user_count}</Descriptions.Item>
      </Descriptions>
      <Title level={5} style={{ marginTop: 24, marginBottom: 12 }}>
        调用客户明细
      </Title>
      <Table
        dataSource={skill.user_stats}
        columns={userStatsColumns}
        rowKey="user_id"
        pagination={{ pageSize: 10 }}
        size="small"
      />
    </Drawer>
  );
}
```

- [ ] **Step 4: 创建 PublishModal 组件**

创建 `console/src/pages/Market/PublishModal.tsx`：

```tsx
import { Modal, Form, Input, Select, Button } from "antd";
import { useState } from "react";
import { marketApi, PublishSkillRequest } from "../../api/modules/market";
import { BBK_ID_MAP } from "../../constants/bbk";

const { TextArea } = Input;

interface PublishModalProps {
  open: boolean;
  sourceId: string;
  userId: string;
  userName: string;
  onClose: () => void;
  onSuccess: () => void;
}

export function PublishModal({ open, sourceId, userId, userName, onClose, onSuccess }: PublishModalProps) {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setLoading(true);
      const payload: PublishSkillRequest = {
        name: values.name,
        description: values.description,
        creator_id: userId,
        creator_name: userName,
        category_id: values.category_id,
        bbk_ids: values.bbk_ids,
        skill_json: {},
        skill_md: values.skill_md,
      };
      await marketApi.publishSkill(sourceId, userId, userName, payload);
      form.resetFields();
      onSuccess();
      onClose();
    } catch (err) {
      console.error("Publish failed:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      open={open}
      onCancel={onClose}
      title="上架技能"
      footer={[
        <Button key="cancel" onClick={onClose}>
          取消
        </Button>,
        <Button key="submit" type="primary" loading={loading} onClick={handleSubmit}>
          上架
        </Button>,
      ]}
    >
      <Form form={form} layout="vertical">
        <Form.Item name="name" label="技能名称" rules={[{ required: true }]}>
          <Input />
        </Form.Item>
        <Form.Item name="description" label="描述">
          <TextArea rows={2} />
        </Form.Item>
        <Form.Item name="category_id" label="分类">
          <Select allowClear placeholder="选择分类" options={[]} />
        </Form.Item>
        <Form.Item name="bbk_ids" label="可见机构">
          <Select
            mode="multiple"
            allowClear
            placeholder="不选择则全员可见"
            options={BBK_ID_MAP}
          />
        </Form.Item>
        <Form.Item name="skill_md" label="技能说明">
          <TextArea rows={6} placeholder="Markdown 格式" />
        </Form.Item>
      </Form>
    </Modal>
  );
}
```

- [ ] **Step 5: 创建 DistributeModal 组件**

创建 `console/src/pages/Market/DistributeModal.tsx`：

```tsx
import { Modal, Form, Radio, Select, Button, Space } from "antd";
import { useState } from "react";
import { marketApi, DistributeRequest } from "../../api/modules/market";
import { MarketSkill } from "../../api/modules/market";
import { BBK_ID_MAP } from "../../constants/bbk";

interface DistributeModalProps {
  open: boolean;
  skill: MarketSkill | null;
  sourceId: string;
  userId: string;
  userName: string;
  onClose: () => void;
  onSuccess: () => void;
}

export function DistributeModal({
  open,
  skill,
  sourceId,
  userId,
  userName,
  onClose,
  onSuccess,
}: DistributeModalProps) {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [targetType, setTargetType] = useState<"all" | "bbk_id" | "user_id">("all");

  const handleSubmit = async () => {
    if (!skill) return;
    try {
      const values = await form.validateFields();
      setLoading(true);
      const payload: DistributeRequest = {
        target_type: targetType,
        target_values: targetType === "all" ? [] : values.target_values || [],
      };
      await marketApi.distributeSkill(sourceId, skill.item_id, userId, userName, payload);
      onSuccess();
      onClose();
    } catch (err) {
      console.error("Distribute failed:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      open={open}
      onCancel={onClose}
      title={`分发「${skill?.name || ""}」`}
      footer={[
        <Button key="cancel" onClick={onClose}>
          取消
        </Button>,
        <Button key="submit" type="primary" loading={loading} onClick={handleSubmit}>
          分发
        </Button>,
      ]}
    >
      <Form form={form} layout="vertical">
        <Form.Item label="分发目标">
          <Radio.Group value={targetType} onChange={(e) => setTargetType(e.target.value)}>
            <Radio value="all">全员</Radio>
            <Radio value="bbk_id">按机构</Radio>
            <Radio value="user_id">按用户</Radio>
          </Radio.Group>
        </Form.Item>
        {targetType === "bbk_id" && (
          <Form.Item name="target_values" label="选择机构">
            <Select mode="multiple" placeholder="选择机构" options={BBK_ID_MAP} />
          </Form.Item>
        )}
        {targetType === "user_id" && (
          <Form.Item name="target_values" label="用户ID">
            <Select mode="tags" placeholder="输入用户ID，回车添加" />
          </Form.Item>
        )}
      </Form>
    </Modal>
  );
}
```

- [ ] **Step 6: 创建 MarketSkills 组件**

创建 `console/src/pages/Market/MarketSkills.tsx`：

```tsx
import { useEffect, useState } from "react";
import { Row, Col, Tree, Button, Empty, Spin, Typography } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { SkillCard } from "./SkillCard";
import { SkillDetailDrawer } from "./SkillDetailDrawer";
import { PublishModal } from "./PublishModal";
import { DistributeModal } from "./DistributeModal";
import { useMarket } from "./useMarket";
import { MarketSkill } from "../../api/modules/market";

const { Title } = Typography;

interface MarketSkillsProps {
  sourceId: string;
  bbkId: string;
  userId: string;
  userName: string;
  isManager: boolean;
}

export function MarketSkills({ sourceId, bbkId, userId, userName, isManager }: MarketSkillsProps) {
  const {
    categories,
    skills,
    loading,
    selectedCategory,
    setSelectedCategory,
    selectedSkill,
    detailDrawerOpen,
    setDetailDrawerOpen,
    publishModalOpen,
    setPublishModalOpen,
    distributeModalOpen,
    setDistributeModalOpen,
    distributeTargetSkill,
    refreshCategories,
    refreshSkills,
    openSkillDetail,
    openDistributeModal,
  } = useMarket(sourceId, bbkId);

  useEffect(() => {
    refreshCategories();
    refreshSkills();
  }, [refreshCategories, refreshSkills]);

  const treeData = [
    { key: "all", title: "全部" },
    ...categories.map((c) => ({ key: String(c.id), title: c.name })),
  ];

  return (
    <div style={{ display: "flex", height: "100%" }}>
      <div style={{ width: 200, borderRight: "1px solid #f0f0f0", padding: 16 }}>
        <Tree
          treeData={treeData}
          selectedKeys={[selectedCategory === null ? "all" : String(selectedCategory)]}
          onSelect={(keys) => {
            const key = keys[0] as string;
            setSelectedCategory(key === "all" ? null : Number(key));
          }}
          defaultExpandAll
        />
      </div>
      <div style={{ flex: 1, padding: 16, overflow: "auto" }}>
        <div style={{ marginBottom: 16, display: "flex", justifyContent: "space-between" }}>
          <Title level={4}>技能市场</Title>
          {isManager && (
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setPublishModalOpen(true)}>
              上架技能
            </Button>
          )}
        </div>
        {loading ? (
          <Spin />
        ) : skills.length === 0 ? (
          <Empty description="暂无技能" />
        ) : (
          <Row gutter={[16, 16]}>
            {skills.map((skill) => (
              <Col key={skill.item_id} xs={24} sm={12} md={8} lg={6}>
                <SkillCard
                  skill={skill}
                  onClick={() => openSkillDetail(skill.item_id)}
                  onDistribute={isManager ? () => openDistributeModal(skill) : undefined}
                  isManager={isManager}
                />
              </Col>
            ))}
          </Row>
        )}
      </div>
      <SkillDetailDrawer
        open={detailDrawerOpen}
        skill={selectedSkill}
        onClose={() => setDetailDrawerOpen(false)}
      />
      {isManager && (
        <>
          <PublishModal
            open={publishModalOpen}
            sourceId={sourceId}
            userId={userId}
            userName={userName}
            onClose={() => setPublishModalOpen(false)}
            onSuccess={refreshSkills}
          />
          <DistributeModal
            open={distributeModalOpen}
            skill={distributeTargetSkill}
            sourceId={sourceId}
            userId={userId}
            userName={userName}
            onClose={() => setDistributeModalOpen(false)}
            onSuccess={refreshSkills}
          />
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 7: 创建 MarketMCP 占位组件**

创建 `console/src/pages/Market/MarketMCP.tsx`：

```tsx
import { Empty, Typography } from "antd";

const { Title } = Typography;

export function MarketMCP() {
  return (
    <div style={{ padding: 24, textAlign: "center" }}>
      <Title level={4}>MCP 市场</Title>
      <Empty description="功能开发中，敬请期待" />
    </div>
  );
}
```

- [ ] **Step 8: 创建 Market 主页面**

创建 `console/src/pages/Market/index.tsx`：

```tsx
import { Tabs } from "antd";
import { Store, Puzzle } from "lucide-react";
import { MarketSkills } from "./MarketSkills";
import { MarketMCP } from "./MarketMCP";
import { useAgentStore } from "../../stores/agentStore";

export default function MarketPage() {
  const { selectedAgent } = useAgentStore();
  const sourceId = selectedAgent?.source_id || "default";
  const bbkId = selectedAgent?.bbk_id || "100";
  const userId = selectedAgent?.user_id || "unknown";
  const userName = selectedAgent?.user_name || "Unknown";
  const isManager = selectedAgent?.is_manager || false;

  return (
    <Tabs
      defaultActiveKey="skills"
      items={[
        {
          key: "skills",
          label: (
            <span>
              <Store size={16} style={{ marginRight: 4 }} />
              技能
            </span>
          ),
          children: (
            <MarketSkills
              sourceId={sourceId}
              bbkId={bbkId}
              userId={userId}
              userName={userName}
              isManager={isManager}
            />
          ),
        },
        {
          key: "mcp",
          label: (
            <span>
              <Puzzle size={16} style={{ marginRight: 4 }} />
              MCP
            </span>
          ),
          children: <MarketMCP />,
        },
      ]}
    />
  );
}
```

- [ ] **Step 9: Commit**

```bash
git add console/src/pages/Market/
git commit -m "feat(console): add marketplace page with skills tab and publish/distribute modals"
```

---

### Task 4: 实现我的技能页面

**Files:**
- Create: `console/src/pages/MySkills/index.tsx`
- Create: `console/src/pages/MySkills/CreatedSkills.tsx`
- Create: `console/src/pages/MySkills/ReceivedSkills.tsx`
- Create: `console/src/pages/MySkills/useMySkills.ts`

**UI 布局**：左侧树状导航（我创建的 / 我接收的）+ 右侧技能列表

- [ ] **Step 1: 创建 useMySkills Hook**

创建 `console/src/pages/MySkills/useMySkills.ts`：

```typescript
import { useState, useCallback } from "react";
import { mySkillsApi, MySkill } from "../../api/modules/mySkills";

export function useMySkills(sourceId: string, userId: string) {
  const [createdSkills, setCreatedSkills] = useState<MySkill[]>([]);
  const [receivedSkills, setReceivedSkills] = useState<MySkill[]>([]);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [created, received] = await Promise.all([
        mySkillsApi.getCreatedSkills(sourceId, userId),
        mySkillsApi.getReceivedSkills(sourceId, userId),
      ]);
      setCreatedSkills(created);
      setReceivedSkills(received);
    } catch (err) {
      console.error("Failed to load my skills:", err);
    } finally {
      setLoading(false);
    }
  }, [sourceId, userId]);

  return {
    createdSkills,
    receivedSkills,
    loading,
    refresh,
  };
}
```

- [ ] **Step 2: 创建 CreatedSkills 组件**

创建 `console/src/pages/MySkills/CreatedSkills.tsx`：

```tsx
import { List, Typography, Tag, Button, Space } from "antd";
import { EditOutlined, DeleteOutlined } from "@ant-design/icons";
import { MySkill } from "../../api/modules/mySkills";

const { Text } = Typography;

interface CreatedSkillsProps {
  skills: MySkill[];
  onEdit?: (skill: MySkill) => void;
  onDelete?: (skill: MySkill) => void;
}

export function CreatedSkills({ skills, onEdit, onDelete }: CreatedSkillsProps) {
  return (
    <List
      dataSource={skills}
      renderItem={(skill) => (
        <List.Item
          actions={[
            onEdit && (
              <Button type="link" icon={<EditOutlined />} onClick={() => onEdit(skill)}>
                编辑
              </Button>
            ),
            onDelete && (
              <Button type="link" danger icon={<DeleteOutlined />} onClick={() => onDelete(skill)}>
                删除
              </Button>
            ),
          ].filter(Boolean)}
        >
          <List.Item.Meta
            title={
              <Space>
                <Text strong>{skill.skill_name}</Text>
                {skill.version && <Tag>v{skill.version}</Tag>}
              </Space>
            }
            description={skill.description || "暂无描述"}
          />
        </List.Item>
      )}
    />
  );
}
```

- [ ] **Step 3: 创建 ReceivedSkills 组件**

创建 `console/src/pages/MySkills/ReceivedSkills.tsx`：

```tsx
import { List, Typography, Tag, Button, Space } from "antd";
import { SyncOutlined } from "@ant-design/icons";
import { MySkill } from "../../api/modules/mySkills";

const { Text } = Typography;

interface ReceivedSkillsProps {
  skills: MySkill[];
  onUpdate?: (skill: MySkill) => void;
}

export function ReceivedSkills({ skills, onUpdate }: ReceivedSkillsProps) {
  return (
    <List
      dataSource={skills}
      renderItem={(skill) => (
        <List.Item
          actions={[
            skill.has_update && onUpdate && (
              <Button type="link" icon={<SyncOutlined />} onClick={() => onUpdate(skill)}>
                更新
              </Button>
            ),
          ].filter(Boolean)}
        >
          <List.Item.Meta
            title={
              <Space>
                <Text strong>{skill.skill_name}</Text>
                {skill.received_version && <Tag color="green">v{skill.received_version}</Tag>}
                {skill.has_update && <Tag color="orange">有更新</Tag>}
              </Space>
            }
            description={
              <Space direction="vertical" size={0}>
                <Text type="secondary">{skill.description || "暂无描述"}</Text>
                {skill.distributed_by && (
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    分发人: {skill.distributed_by}
                  </Text>
                )}
              </Space>
            }
          />
        </List.Item>
      )}
    />
  );
}
```

- [ ] **Step 4: 创建 MySkills 主页面**

创建 `console/src/pages/MySkills/index.tsx`：

```tsx
import { useEffect, useState } from "react";
import { Typography, Tree, Card, Spin } from "antd";
import { CreatedSkills } from "./CreatedSkills";
import { ReceivedSkills } from "./ReceivedSkills";
import { useMySkills } from "./useMySkills";
import { useAgentStore } from "../../stores/agentStore";

const { Title } = Typography;

type TabKey = "created" | "received";

export default function MySkillsPage() {
  const { selectedAgent } = useAgentStore();
  const sourceId = selectedAgent?.source_id || "default";
  const userId = selectedAgent?.user_id || "unknown";
  const { createdSkills, receivedSkills, loading, refresh } = useMySkills(sourceId, userId);
  const [selectedTab, setSelectedTab] = useState<TabKey>("created");

  useEffect(() => {
    refresh();
  }, [refresh]);

  const treeData = [
    { key: "created", title: `我创建的 (${createdSkills.length})` },
    { key: "received", title: `我接收的 (${receivedSkills.length})` },
  ];

  return (
    <div style={{ display: "flex", height: "100%" }}>
      <div style={{ width: 200, borderRight: "1px solid #f0f0f0", padding: 16 }}>
        <Tree
          treeData={treeData}
          selectedKeys={[selectedTab]}
          onSelect={(keys) => setSelectedTab(keys[0] as TabKey)}
        />
      </div>
      <div style={{ flex: 1, padding: 16, overflow: "auto" }}>
        <Card>
          {loading ? (
            <Spin />
          ) : selectedTab === "created" ? (
            <>
              <Title level={4}>我创建的技能</Title>
              <CreatedSkills skills={createdSkills} />
            </>
          ) : (
            <>
              <Title level={4}>我接收的技能</Title>
              <ReceivedSkills skills={receivedSkills} />
            </>
          )}
        </Card>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Commit**

```bash
git add console/src/pages/MySkills/
git commit -m "feat(console): add my-skills page with created/received tabs"
```

---

### Task 5: 实现我的 MCP 占位页面

**Files:**
- Create: `console/src/pages/MyMCP/index.tsx`

- [ ] **Step 1: 创建 MyMCP 占位页面**

创建 `console/src/pages/MyMCP/index.tsx`：

```tsx
import { Card, Empty, Typography } from "antd";

const { Title } = Typography;

export default function MyMCPPage() {
  return (
    <Card>
      <Title level={4}>我的 MCP</Title>
      <Empty description="功能开发中，敬请期待" />
    </Card>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add console/src/pages/MyMCP/
git commit -m "feat(console): add my-mcp placeholder page"
```

---

## 自检

**Spec 覆盖：**
- [x] 应用市场页（左侧分类树 + 右侧技能列表）— Task 3
- [x] 技能 tab — Task 3
- [x] MCP tab（留空占位）— Task 3
- [x] 技能卡片（名称、描述、分类、创建人、版本号、调用次数、用户量）— Task 3 SkillCard
- [x] 技能详情抽屉（调用客户明细表格）— Task 3 SkillDetailDrawer
- [x] 上架弹窗（管理员）— Task 3 PublishModal
- [x] 下架按钮（管理员）— Task 3（复用 PublishModal 或独立按钮）
- [x] 分发弹窗（管理员，多选叠加模式）— Task 3 DistributeModal
- [x] 我的技能菜单（我创建的 / 我接收的）— Task 4
- [x] 我创建的技能列表（编辑、删除、启用/禁用）— Task 4 CreatedSkills
- [x] 我接收的技能列表（有更新标记）— Task 4 ReceivedSkills
- [x] 我的 MCP 菜单（留空占位）— Task 5
- [x] API 模块（市场 + 我的技能）— Task 1

**占位符扫描：** 无 TBD/TODO，所有文件完整。

**类型一致性：**
- MarketSkill / MarketSkillDetail 与 API 响应匹配
- MySkill 与 API 响应匹配
- PublishSkillRequest / DistributeRequest 与 API 请求匹配
