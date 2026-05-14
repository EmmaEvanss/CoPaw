# MCP 应用市场 - 计划 C：前端

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现我的 MCP 页面和市场 MCP Tab，包括列表、详情、创建、编辑、启停、删除、测试连接、发布和分发等完整功能。

**Architecture:** 沿用 `CmbCoworkAgent-main` 项目的交互模式。我的 MCP 使用 Master-Detail 布局，市场 MCP 复用现有 Market 页面的技能 / MCP Tab 切换结构。

**Tech Stack:** React, TypeScript, Ant Design, Vite

**依赖:** 计划 A + 计划 B（后端 API）已完成

---

## 文件结构

| 文件 | 操作 | 说明 |
|------|------|------|
| `console/src/api/modules/myMcp.ts` | Create | 我的 MCP API 模块 |
| `console/src/api/modules/marketMcp.ts` | Create | 市场 MCP API 模块（或扩展 market.ts） |
| `console/src/api/types/myMcp.ts` | Create | 我的 MCP 类型定义 |
| `console/src/api/types/marketMcp.ts` | Create | 市场 MCP 类型定义 |
| `console/src/pages/MyMCP/index.tsx` | Modify | 替换占位页为正式页面 |
| `console/src/pages/MyMCP/MCPDetailPanel.tsx` | Create | MCP 详情面板组件 |
| `console/src/pages/MyMCP/MCPFormModal.tsx` | Create | MCP 创建/编辑表单弹窗 |
| `console/src/pages/Market/MarketMCP.tsx` | Modify | 补完 MCP 分支 |
| `console/src/pages/Market/MCPDetailDrawer.tsx` | Create | 市场 MCP 详情抽屉 |
| `console/src/pages/Market/MCPUploadModal.tsx` | Create | MCP 上传弹窗 |

---

## Task 1: 创建 API 类型定义

**Files:**
- Create: `console/src/api/types/myMcp.ts`
- Create: `console/src/api/types/marketMcp.ts`
- Modify: `console/src/api/types/index.ts`

- [ ] **Step 1: 创建我的 MCP 类型定义**

```typescript
// console/src/api/types/myMcp.ts

export interface MyMCPListItem {
  client_key: string;
  name: string;
  description: string;
  transport: "stdio" | "streamable_http" | "sse";
  enabled: boolean;
  source: string;
  market_client_key: string;
  created_at: string;
  updated_at: string;
}

export interface MyMCPDetail extends MyMCPListItem {
  url: string;
  headers: Record<string, string>;
  command: string;
  args: string[];
  env: Record<string, string>;
  cwd: string;
  lazy_load: boolean;
  distributed_by: string;
}

export interface MyMCPCreateRequest {
  client_key: string;
  name: string;
  description?: string;
  transport?: "stdio" | "streamable_http" | "sse";
  url?: string;
  headers?: Record<string, string>;
  command?: string;
  args?: string[];
  env?: Record<string, string>;
  cwd?: string;
}

export interface MyMCPUpdateRequest {
  name?: string;
  description?: string;
  transport?: "stdio" | "streamable_http" | "sse";
  url?: string;
  headers?: Record<string, string>;
  command?: string;
  args?: string[];
  env?: Record<string, string>;
  cwd?: string;
}

export interface PublishMCPRequest {
  client_keys: string[];
  category_id?: number;
  bbk_ids?: string[];
}

export interface PublishMCPResult {
  client_key: string;
  item_id?: string;
  success: boolean;
  error?: string;
}

export interface PublishMCPResponse {
  results: PublishMCPResult[];
}

export interface MCPTestResult {
  success: boolean;
  tools: Array<{ name: string; description: string }>;
  error?: string;
}
```

- [ ] **Step 2: 创建市场 MCP 类型定义**

```typescript
// console/src/api/types/marketMcp.ts

export interface MarketMCPItem {
  item_id: string;
  client_key: string;
  name: string;
  description: string;
  creator_id: string;
  creator_name: string;
  category_id: number | null;
  bbk_ids: string[];
  created_at: string | null;
  updated_at: string | null;
  call_count: number;
  user_count: number;
}

export interface MCPConfigDetail {
  transport: "stdio" | "streamable_http" | "sse";
  url: string;
  headers: Record<string, string>;
  command: string;
  args: string[];
  env: Record<string, string>;
  cwd: string;
  lazy_load: boolean;
}

export interface MCPUserStat {
  user_id: string;
  user_name: string;
  call_count: number;
}

export interface MarketMCPDetail extends MarketMCPItem {
  config: MCPConfigDetail;
  user_stats: MCPUserStat[];
}

export interface UploadMCPResponse {
  success: boolean;
  error?: string;
}

export interface DistributeRequest {
  target_type: "all" | "bbk_id" | "user_id";
  target_values: string[];
}

export interface DistributeResponse {
  distributed_count: number;
  item_id: string;
}
```

- [ ] **Step 3: 导出类型**

```typescript
// console/src/api/types/index.ts
// 添加导出

export * from "./myMcp";
export * from "./marketMcp";
```

- [ ] **Step 4: 提交**

```bash
git add console/src/api/types/myMcp.ts console/src/api/types/marketMcp.ts console/src/api/types/index.ts
git commit -m "feat(api-types): add MCP type definitions"
```

---

## Task 2: 创建 API 模块

**Files:**
- Create: `console/src/api/modules/myMcp.ts`
- Create: `console/src/api/modules/marketMcp.ts`
- Modify: `console/src/api/index.ts`

- [ ] **Step 1: 创建我的 MCP API 模块**

```typescript
// console/src/api/modules/myMcp.ts

import { request } from "../request";
import { buildAuthHeaders } from "../authHeaders";
import type {
  MyMCPListItem,
  MyMCPDetail,
  MyMCPCreateRequest,
  MyMCPUpdateRequest,
  PublishMCPRequest,
  PublishMCPResponse,
  MCPTestResult,
} from "../types/myMcp";

function mergeHeaders(extra?: Record<string, string>): RequestInit {
  const base = buildAuthHeaders();
  const merged: Record<string, string> = { ...base, ...(extra || {}) };
  return { headers: new Headers(merged) };
}

export const myMcpApi = {
  list: async (): Promise<MyMCPListItem[]> => {
    const opts = mergeHeaders();
    return request<MyMCPListItem[]>("/my-mcp", opts);
  },

  get: async (clientKey: string): Promise<MyMCPDetail | null> => {
    const opts = mergeHeaders();
    return request<MyMCPDetail | null>(`/my-mcp/${encodeURIComponent(clientKey)}`, opts);
  },

  create: async (data: MyMCPCreateRequest): Promise<MyMCPDetail> => {
    const opts: RequestInit = {
      method: "POST",
      headers: new Headers({
        "Content-Type": "application/json",
      }),
      body: JSON.stringify(data),
      ...mergeHeaders(),
    };
    return request<MyMCPDetail>("/my-mcp", opts);
  },

  update: async (clientKey: string, data: MyMCPUpdateRequest): Promise<MyMCPDetail> => {
    const opts: RequestInit = {
      method: "PUT",
      headers: new Headers({
        "Content-Type": "application/json",
      }),
      body: JSON.stringify(data),
      ...mergeHeaders(),
    };
    return request<MyMCPDetail>(`/my-mcp/${encodeURIComponent(clientKey)}`, opts);
  },

  delete: async (clientKey: string): Promise<void> => {
    const opts: RequestInit = {
      method: "DELETE",
      ...mergeHeaders(),
    };
    return request<void>(`/my-mcp/${encodeURIComponent(clientKey)}`, opts);
  },

  toggle: async (clientKey: string): Promise<MyMCPDetail> => {
    const opts: RequestInit = {
      method: "PATCH",
      ...mergeHeaders(),
    };
    return request<MyMCPDetail>(`/my-mcp/${encodeURIComponent(clientKey)}/toggle`, opts);
  },

  test: async (clientKey: string): Promise<MCPTestResult> => {
    const opts: RequestInit = {
      method: "POST",
      ...mergeHeaders(),
    };
    return request<MCPTestResult>(`/my-mcp/${encodeURIComponent(clientKey)}/test`, opts);
  },

  publish: async (data: PublishMCPRequest): Promise<PublishMCPResponse> => {
    const opts: RequestInit = {
      method: "POST",
      headers: new Headers({
        "Content-Type": "application/json",
        "X-Manager": "true",
      }),
      body: JSON.stringify(data),
      ...mergeHeaders(),
    };
    return request<PublishMCPResponse>("/my-mcp/publish", opts);
  },
};
```

- [ ] **Step 2: 创建市场 MCP API 模块**

```typescript
// console/src/api/modules/marketMcp.ts

import { request } from "../request";
import { buildAuthHeaders } from "../authHeaders";
import type {
  MarketMCPItem,
  MarketMCPDetail,
  UploadMCPResponse,
  DistributeRequest,
  DistributeResponse,
  MCPTestResult,
} from "../types/marketMcp";

function mergeHeaders(extra?: Record<string, string>): RequestInit {
  const base = buildAuthHeaders();
  const merged: Record<string, string> = { ...base, ...(extra || {}) };
  return { headers: new Headers(merged) };
}

export const marketMcpApi = {
  list: async (
    sourceId: string,
    bbkId: string,
    categoryId?: number
  ): Promise<MarketMCPItem[]> => {
    let url = "/market/mcp";
    const params = new URLSearchParams();
    if (categoryId !== undefined) {
      params.append("category_id", String(categoryId));
    }
    if (params.toString()) {
      url += `?${params.toString()}`;
    }
    const opts = mergeHeaders({
      "X-Source-Id": sourceId,
      "X-Bbk-Id": bbkId,
    });
    return request<MarketMCPItem[]>(url, opts);
  },

  getDetail: async (
    sourceId: string,
    itemId: string,
    bbkId: string
  ): Promise<MarketMCPDetail | null> => {
    const opts = mergeHeaders({
      "X-Source-Id": sourceId,
      "X-Bbk-Id": bbkId,
    });
    return request<MarketMCPDetail | null>(`/market/mcp/${itemId}`, opts);
  },

  upload: async (
    sourceId: string,
    userId: string,
    userName: string,
    file: File,
    name?: string,
    description?: string,
    categoryId?: number,
    bbkIds?: string[]
  ): Promise<UploadMCPResponse> => {
    const formData = new FormData();
    formData.append("file", file);
    if (name) formData.append("name", name);
    if (description) formData.append("description", description);
    if (categoryId) formData.append("category_id", String(categoryId));
    if (bbkIds) formData.append("bbk_ids", JSON.stringify(bbkIds));

    const opts: RequestInit = {
      method: "POST",
      headers: new Headers({
        "X-Source-Id": sourceId,
        "X-User-Id": userId,
        "X-User-Name": encodeURIComponent(userName),
        "X-Manager": "true",
      }),
      body: formData,
    };
    return request<UploadMCPResponse>("/market/mcp/upload", opts);
  },

  distribute: async (
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
    return request<DistributeResponse>(`/market/mcp/${itemId}/distribute`, opts);
  },

  delete: async (
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
    return request<void>(`/market/mcp/${itemId}`, opts);
  },

  test: async (
    sourceId: string,
    itemId: string
  ): Promise<MCPTestResult> => {
    const opts: RequestInit = {
      method: "POST",
      headers: new Headers({
        "X-Source-Id": sourceId,
      }),
    };
    return request<MCPTestResult>(`/market/mcp/${itemId}/test`, opts);
  },
};
```

- [ ] **Step 3: 导出 API 模块**

```typescript
// console/src/api/index.ts
// 添加导出

import { myMcpApi } from "./modules/myMcp";
import { marketMcpApi } from "./modules/marketMcp";

export { myMcpApi, marketMcpApi };
```

- [ ] **Step 4: 提交**

```bash
git add console/src/api/modules/myMcp.ts console/src/api/modules/marketMcp.ts console/src/api/index.ts
git commit -m "feat(api): add myMcp and marketMcp API modules"
```

---

## Task 3: 实现我的 MCP 页面主框架

**Files:**
- Modify: `console/src/pages/MyMCP/index.tsx`

- [ ] **Step 1: 实现页面主框架**

```typescript
// console/src/pages/MyMCP/index.tsx

import React, { useState, useEffect, useCallback } from "react";
import {
  Layout,
  List,
  Input,
  Button,
  Tag,
  Empty,
  Spin,
  message,
  Popconfirm,
  Space,
  Typography,
} from "antd";
import {
  PlusOutlined,
  ReloadOutlined,
  CloudUploadOutlined,
  DeleteOutlined,
  PlayCircleOutlined,
  PauseCircleOutlined,
} from "@ant-design/icons";

import { myMcpApi } from "../../api";
import type { MyMCPListItem, MyMCPDetail } from "../../api/types/myMcp";
import { MCPDetailPanel } from "./MCPDetailPanel";
import { MCPFormModal } from "./MCPFormModal";
import { getUserId, isManager } from "../../utils/identity";

const { Sider, Content } = Layout;
const { Search } = Input;
const { Text } = Typography;

export default function MyMCPPage() {
  const [loading, setLoading] = useState(false);
  const [mcpList, setMcpList] = useState<MyMCPListItem[]>([]);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [selectedDetail, setSelectedDetail] = useState<MyMCPDetail | null>(null);
  const [searchText, setSearchText] = useState("");
  const [formVisible, setFormVisible] = useState(false);
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const manager = isManager();

  // 加载列表
  const loadList = useCallback(async () => {
    setLoading(true);
    try {
      const data = await myMcpApi.list();
      setMcpList(data);
      if (data.length > 0 && !selectedKey) {
        setSelectedKey(data[0].client_key);
      }
    } catch (err) {
      message.error("加载 MCP 列表失败");
    } finally {
      setLoading(false);
    }
  }, [selectedKey]);

  // 加载详情
  const loadDetail = useCallback(async (clientKey: string) => {
    try {
      const detail = await myMcpApi.get(clientKey);
      setSelectedDetail(detail);
    } catch (err) {
      message.error("加载 MCP 详情失败");
    }
  }, []);

  useEffect(() => {
    loadList();
  }, [loadList]);

  useEffect(() => {
    if (selectedKey) {
      loadDetail(selectedKey);
    }
  }, [selectedKey, loadDetail]);

  // 过滤列表
  const filteredList = mcpList.filter((item) =>
    item.name.toLowerCase().includes(searchText.toLowerCase())
  );

  // 判断来源
  const isCreatedByMe = (item: MyMCPListItem) => item.source === "";
  const isDistributed = (item: MyMCPListItem) => item.source.startsWith("marketplace:");

  // 切换启用状态
  const handleToggle = async (clientKey: string) => {
    try {
      await myMcpApi.toggle(clientKey);
      message.success("状态已切换");
      loadList();
      if (selectedKey === clientKey) {
        loadDetail(clientKey);
      }
    } catch (err) {
      message.error("切换失败");
    }
  };

  // 删除
  const handleDelete = async (clientKey: string) => {
    try {
      await myMcpApi.delete(clientKey);
      message.success("已删除");
      loadList();
      if (selectedKey === clientKey) {
        setSelectedKey(null);
        setSelectedDetail(null);
      }
    } catch (err) {
      message.error("删除失败");
    }
  };

  // 创建成功回调
  const handleCreateSuccess = () => {
    setFormVisible(false);
    setEditingKey(null);
    loadList();
  };

  return (
    <Layout style={{ height: "100%", background: "#fff" }}>
      <Sider width={300} style={{ background: "#fafafa", borderRight: "1px solid #e8e8e8" }}>
        <div style={{ padding: 16 }}>
          <Space direction="vertical" style={{ width: "100%" }}>
            <Search
              placeholder="搜索 MCP 名称"
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              allowClear
            />
            <Space>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={() => {
                  setEditingKey(null);
                  setFormVisible(true);
                }}
              >
                创建
              </Button>
              <Button icon={<ReloadOutlined />} onClick={loadList}>
                刷新
              </Button>
              {manager && selectedKey && isCreatedByMe(mcpList.find((i) => i.client_key === selectedKey)!) && (
                <Button icon={<CloudUploadOutlined />} onClick={() => {/* 发布逻辑 */}}>
                  发布
                </Button>
              )}
            </Space>
          </Space>
        </div>

        <Spin spinning={loading}>
          {filteredList.length === 0 ? (
            <Empty description="暂无 MCP" style={{ marginTop: 40 }} />
          ) : (
            <List
              dataSource={filteredList}
              renderItem={(item) => (
                <List.Item
                  onClick={() => setSelectedKey(item.client_key)}
                  style={{
                    padding: "12px 16px",
                    cursor: "pointer",
                    background: selectedKey === item.client_key ? "#e6f7ff" : "transparent",
                  }}
                >
                  <List.Item.Meta
                    title={
                      <Space>
                        <Text strong>{item.name}</Text>
                        {isCreatedByMe(item) ? (
                          <Tag color="blue">我创建</Tag>
                        ) : (
                          <Tag color="orange">市场分发</Tag>
                        )}
                        {!item.enabled && <Tag color="red">已禁用</Tag>}
                      </Space>
                    }
                    description={item.description || item.client_key}
                  />
                </List.Item>
              )}
            />
          )}
        </Spin>
      </Sider>

      <Content style={{ padding: 24 }}>
        {selectedDetail ? (
          <MCPDetailPanel
            detail={selectedDetail}
            isCreatedByMe={isCreatedByMe(selectedDetail)}
            manager={manager}
            onToggle={() => handleToggle(selectedDetail.client_key)}
            onDelete={() => handleDelete(selectedDetail.client_key)}
            onEdit={() => {
              setEditingKey(selectedDetail.client_key);
              setFormVisible(true);
            }}
            onTest={() => {/* 测试连接 */}}
            onPublish={() => {/* 发布 */}}
          />
        ) : (
          <Empty description="请选择 MCP" style={{ marginTop: 100 }} />
        )}
      </Content>

      <MCPFormModal
        visible={formVisible}
        editingKey={editingKey}
        detail={editingKey ? selectedDetail : null}
        onSuccess={handleCreateSuccess}
        onCancel={() => {
          setFormVisible(false);
          setEditingKey(null);
        }}
      />
    </Layout>
  );
}
```

- [ ] **Step 2: 提交**

```bash
git add console/src/pages/MyMCP/index.tsx
git commit -m "feat(my-mcp): implement main page layout with list and detail"
```

---

## Task 4: 实现 MCP 详情面板组件

**Files:**
- Create: `console/src/pages/MyMCP/MCPDetailPanel.tsx`

- [ ] **Step 1: 创建详情面板组件**

```typescript
// console/src/pages/MyMCP/MCPDetailPanel.tsx

import React, { useState } from "react";
import {
  Card,
  Descriptions,
  Button,
  Space,
  Tag,
  Popconfirm,
  message,
  Modal,
  List,
  Spin,
  Typography,
} from "antd";
import {
  EditOutlined,
  DeleteOutlined,
  PlayCircleOutlined,
  PauseCircleOutlined,
  CloudUploadOutlined,
  ApiOutlined,
} from "@ant-design/icons";

import type { MyMCPDetail, MCPTestResult } from "../../api/types/myMcp";
import { myMcpApi } from "../../api";

const { Text, Paragraph } = Typography;

interface MCPDetailPanelProps {
  detail: MyMCPDetail;
  isCreatedByMe: boolean;
  manager: boolean;
  onToggle: () => void;
  onDelete: () => void;
  onEdit: () => void;
  onTest: () => void;
  onPublish: () => void;
}

export function MCPDetailPanel({
  detail,
  isCreatedByMe,
  manager,
  onToggle,
  onDelete,
  onEdit,
  onTest,
  onPublish,
}: MCPDetailPanelProps) {
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<MCPTestResult | null>(null);
  const [testModalVisible, setTestModalVisible] = useState(false);

  const handleTest = async () => {
    setTesting(true);
    try {
      const result = await myMcpApi.test(detail.client_key);
      setTestResult(result);
      setTestModalVisible(true);
    } catch (err) {
      message.error("测试连接失败");
    } finally {
      setTesting(false);
    }
  };

  return (
    <Card
      title={
        <Space>
          <Text strong style={{ fontSize: 18 }}>{detail.name}</Text>
          {isCreatedByMe ? (
            <Tag color="blue">我创建</Tag>
          ) : (
            <Tag color="orange">市场分发</Tag>
          )}
          {detail.enabled ? (
            <Tag color="green">已启用</Tag>
          ) : (
            <Tag color="red">已禁用</Tag>
          )}
        </Space>
      }
      extra={
        <Space>
          {isCreatedByMe && (
            <Button icon={<EditOutlined />} onClick={onEdit}>
              编辑
            </Button>
          )}
          <Button
            icon={detail.enabled ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
            onClick={onToggle}
          >
            {detail.enabled ? "禁用" : "启用"}
          </Button>
          <Button
            icon={<ApiOutlined />}
            loading={testing}
            onClick={handleTest}
          >
            测试连接
          </Button>
          {isCreatedByMe && manager && (
            <Button icon={<CloudUploadOutlined />} onClick={onPublish}>
              发布
            </Button>
          )}
          <Popconfirm
            title="确定删除此 MCP？"
            onConfirm={onDelete}
            okText="删除"
            cancelText="取消"
          >
            <Button danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      }
    >
      <Descriptions column={2} bordered size="small">
        <Descriptions.Item label="client_key">{detail.client_key}</Descriptions.Item>
        <Descriptions.Item label="传输类型">{detail.transport}</Descriptions.Item>
        <Descriptions.Item label="描述">{detail.description || "-"}</Descriptions.Item>
        <Descriptions.Item label="创建时间">{detail.created_at || "-"}</Descriptions.Item>
        <Descriptions.Item label="更新时间">{detail.updated_at || "-"}</Descriptions.Item>
        <Descriptions.Item label="来源">
          {isCreatedByMe ? "我创建的" : `市场分发 (${detail.distributed_by})`}
        </Descriptions.Item>

        {detail.transport === "stdio" && (
          <>
            <Descriptions.Item label="命令">{detail.command}</Descriptions.Item>
            <Descriptions.Item label="参数">
              <Paragraph copyable>{detail.args.join(" ")}</Paragraph>
            </Descriptions.Item>
            <Descriptions.Item label="工作目录">{detail.cwd || "-"}</Descriptions.Item>
          </>
        )}

        {detail.transport !== "stdio" && (
          <>
            <Descriptions.Item label="URL">{detail.url}</Descriptions.Item>
          </>
        )}

        <Descriptions.Item label="环境变量" span={2}>
          {Object.keys(detail.env).length > 0 ? (
            <Paragraph copyable={{ text: JSON.stringify(detail.env, null, 2) }}>
              <pre style={{ margin: 0, fontSize: 12 }}>
                {JSON.stringify(detail.env, null, 2)}
              </pre>
            </Paragraph>
          ) : "-"}
        </Descriptions.Item>

        <Descriptions.Item label="请求头" span={2}>
          {Object.keys(detail.headers).length > 0 ? (
            <Paragraph copyable={{ text: JSON.stringify(detail.headers, null, 2) }}>
              <pre style={{ margin: 0, fontSize: 12 }}>
                {JSON.stringify(detail.headers, null, 2)}
              </pre>
            </Paragraph>
          ) : "-"}
        </Descriptions.Item>
      </Descriptions>

      {/* 测试结果弹窗 */}
      <Modal
        title="测试连接结果"
        open={testModalVisible}
        onCancel={() => setTestModalVisible(false)}
        footer={<Button onClick={() => setTestModalVisible(false)}>关闭</Button>}
        width={600}
      >
        {testResult?.success ? (
          <>
            <Text type="success">连接成功，可用工具：</Text>
            <List
              dataSource={testResult.tools}
              renderItem={(tool) => (
                <List.Item>
                  <List.Item.Meta
                    title={tool.name}
                    description={tool.description}
                  />
                </List.Item>
              )}
            />
          </>
        ) : (
          <Text type="danger">连接失败：{testResult?.error}</Text>
        )}
      </Modal>
    </Card>
  );
}
```

- [ ] **Step 2: 提交**

```bash
git add console/src/pages/MyMCP/MCPDetailPanel.tsx
git commit -m "feat(my-mcp): add MCP detail panel component"
```

---

## Task 5: 实现 MCP 创建/编辑表单弹窗

**Files:**
- Create: `console/src/pages/MyMCP/MCPFormModal.tsx`

- [ ] **Step 1: 创建表单弹窗组件**

```typescript
// console/src/pages/MyMCP/MCPFormModal.tsx

import React, { useEffect } from "react";
import {
  Modal,
  Form,
  Input,
  Select,
  Button,
  Space,
  message,
} from "antd";

import type { MyMCPDetail, MyMCPCreateRequest, MyMCPUpdateRequest } from "../../api/types/myMcp";
import { myMcpApi } from "../../api";

interface MCPFormModalProps {
  visible: boolean;
  editingKey: string | null;
  detail: MyMCPDetail | null;
  onSuccess: () => void;
  onCancel: () => void;
}

export function MCPFormModal({
  visible,
  editingKey,
  detail,
  onSuccess,
  onCancel,
}: MCPFormModalProps) {
  const [form] = Form.useForm();
  const isEditing = !!editingKey;

  useEffect(() => {
    if (visible) {
      if (isEditing && detail) {
        form.setFieldsValue({
          client_key: detail.client_key,
          name: detail.name,
          description: detail.description,
          transport: detail.transport,
          url: detail.url,
          command: detail.command,
          args: detail.args.join(" "),
          cwd: detail.cwd,
          // env/headers 需要特殊处理（脱敏值）
          env: Object.entries(detail.env).map(([k, v]) => `${k}=${v}`).join("\n"),
          headers: Object.entries(detail.headers).map(([k, v]) => `${k}: ${v}`).join("\n"),
        });
      } else {
        form.resetFields();
        form.setFieldsValue({ transport: "stdio" });
      }
    }
  }, [visible, isEditing, detail, form]);

  const handleSubmit = async (values: any) => {
    try {
      // 解析 env 和 headers
      const env: Record<string, string> = {};
      if (values.env) {
        values.env.split("\n").forEach((line: string) => {
          const [k, v] = line.split("=").map((s) => s.trim());
          if (k && v) env[k] = v;
        });
      }

      const headers: Record<string, string> = {};
      if (values.headers) {
        values.headers.split("\n").forEach((line: string) => {
          const [k, v] = line.split(":").map((s) => s.trim());
          if (k && v) headers[k] = v;
        });
      }

      const args = values.args ? values.args.split(" ").filter(Boolean) : [];

      if (isEditing) {
        const updateData: MyMCPUpdateRequest = {
          name: values.name,
          description: values.description,
          transport: values.transport,
          url: values.url,
          command: values.command,
          args,
          env,
          headers,
          cwd: values.cwd,
        };
        await myMcpApi.update(editingKey!, updateData);
        message.success("更新成功");
      } else {
        const createData: MyMCPCreateRequest = {
          client_key: values.client_key,
          name: values.name,
          description: values.description,
          transport: values.transport,
          url: values.url,
          command: values.command,
          args,
          env,
          headers,
          cwd: values.cwd,
        };
        await myMcpApi.create(createData);
        message.success("创建成功");
      }
      onSuccess();
    } catch (err: any) {
      message.error(err.message || "操作失败");
    }
  };

  return (
    <Modal
      title={isEditing ? "编辑 MCP" : "创建 MCP"}
      open={visible}
      onCancel={onCancel}
      footer={null}
      width={600}
      destroyOnClose
    >
      <Form
        form={form}
        layout="vertical"
        onFinish={handleSubmit}
      >
        {!isEditing && (
          <Form.Item
            name="client_key"
            label="client_key"
            rules={[
              { required: true, message: "请输入 client_key" },
              { pattern: /^[a-zA-Z0-9_-]+$/, message: "只能包含字母、数字、下划线和连字符" },
            ]}
          >
            <Input placeholder="唯一标识，如 weather-tool" disabled={isEditing} />
          </Form.Item>
        )}

        <Form.Item
          name="name"
          label="名称"
          rules={[{ required: true, message: "请输入名称" }]}
        >
          <Input placeholder="显示名称" />
        </Form.Item>

        <Form.Item name="description" label="描述">
          <Input.TextArea placeholder="简要描述" rows={2} />
        </Form.Item>

        <Form.Item name="transport" label="传输类型">
          <Select>
            <Select.Option value="stdio">stdio</Select.Option>
            <Select.Option value="streamable_http">streamable_http</Select.Option>
            <Select.Option value="sse">sse</Select.Option>
          </Select>
        </Form.Item>

        <Form.Item noStyle shouldUpdate={(prev, cur) => prev.transport !== cur.transport}>
          {({ getFieldValue }) => {
            const transport = getFieldValue("transport");
            if (transport === "stdio") {
              return (
                <>
                  <Form.Item
                    name="command"
                    label="命令"
                    rules={[{ required: true, message: "请输入命令" }]}
                  >
                    <Input placeholder="如 npx" />
                  </Form.Item>
                  <Form.Item name="args" label="参数">
                    <Input placeholder="空格分隔，如 -y weather-mcp" />
                  </Form.Item>
                  <Form.Item name="cwd" label="工作目录">
                    <Input placeholder="可选" />
                  </Form.Item>
                </>
              );
            }
            return (
              <Form.Item
                name="url"
                label="URL"
                rules={[{ required: true, message: "请输入 URL" }]}
              >
                <Input placeholder="HTTP/SSE URL" />
              </Form.Item>
            );
          }}
        </Form.Item>

        <Form.Item name="env" label="环境变量">
          <Input.TextArea
            placeholder="每行一个，格式 KEY=value"
            rows={4}
          />
        </Form.Item>

        <Form.Item name="headers" label="请求头">
          <Input.TextArea
            placeholder="每行一个，格式 Key: Value"
            rows={4}
          />
        </Form.Item>

        <Form.Item>
          <Space>
            <Button type="primary" htmlType="submit">
              {isEditing ? "保存" : "创建"}
            </Button>
            <Button onClick={onCancel}>取消</Button>
          </Space>
        </Form.Item>
      </Form>
    </Modal>
  );
}
```

- [ ] **Step 2: 提交**

```bash
git add console/src/pages/MyMCP/MCPFormModal.tsx
git commit -m "feat(my-mcp): add MCP create/edit form modal"
```

---

## Task 6: 实现市场 MCP Tab

**Files:**
- Modify: `console/src/pages/Market/MarketMCP.tsx`

- [ ] **Step 1: 实现市场 MCP Tab**

```typescript
// console/src/pages/Market/MarketMCP.tsx

import React, { useState, useEffect, useCallback } from "react";
import {
  Row,
  Col,
  Card,
  Input,
  Button,
  Space,
  Empty,
  Spin,
  message,
  Tag,
  Typography,
} from "antd";
import {
  ReloadOutlined,
  UploadOutlined,
  AppstoreOutlined,
} from "@ant-design/icons";

import { marketMcpApi, marketApi } from "../../api";
import type { MarketMCPItem, Category } from "../../api/types";
import { MCPDetailDrawer } from "./MCPDetailDrawer";
import { MCPUploadModal } from "./MCPUploadModal";

const { Search } = Input;
const { Text } = Typography;

interface MarketMCPProps {
  sourceId: string;
  bbkId: string;
  userId: string;
  userName: string;
  isManager: boolean;
}

export function MarketMCP({
  sourceId,
  bbkId,
  userId,
  userName,
  isManager,
}: MarketMCPProps) {
  const [loading, setLoading] = useState(false);
  const [mcpList, setMcpList] = useState<MarketMCPItem[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<number | null>(null);
  const [searchText, setSearchText] = useState("");
  const [selectedItemId, setSelectedItemId] = useState<string | null>(null);
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [uploadModalVisible, setUploadModalVisible] = useState(false);

  // 加载分类
  const loadCategories = useCallback(async () => {
    try {
      const data = await marketApi.listCategories(sourceId);
      setCategories(data);
    } catch (err) {
      // 忽略分类加载失败
    }
  }, [sourceId]);

  // 加载列表
  const loadList = useCallback(async () => {
    setLoading(true);
    try {
      const data = await marketMcpApi.list(sourceId, bbkId, selectedCategory);
      setMcpList(data);
    } catch (err) {
      message.error("加载市场 MCP 失败");
    } finally {
      setLoading(false);
    }
  }, [sourceId, bbkId, selectedCategory]);

  useEffect(() => {
    loadCategories();
  }, [loadCategories]);

  useEffect(() => {
    loadList();
  }, [loadList]);

  // 过滤列表
  const filteredList = mcpList.filter((item) =>
    item.name.toLowerCase().includes(searchText.toLowerCase())
  );

  // 点击卡片
  const handleCardClick = (itemId: string) => {
    setSelectedItemId(itemId);
    setDrawerVisible(true);
  };

  // 刷新
  const handleRefresh = () => {
    loadList();
  };

  // 上传成功
  const handleUploadSuccess = () => {
    setUploadModalVisible(false);
    loadList();
  };

  return (
    <div style={{ padding: 24 }}>
      {/* 头部操作栏 */}
      <Space style={{ marginBottom: 16 }} wrap>
        <Search
          placeholder="搜索 MCP 名称"
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          allowClear
          style={{ width: 200 }}
        />
        <Button icon={<ReloadOutlined />} onClick={handleRefresh}>
          刷新
        </Button>
        {isManager && (
          <Button
            type="primary"
            icon={<UploadOutlined />}
            onClick={() => setUploadModalVisible(true)}
          >
            上传连接器
          </Button>
        )}
      </Space>

      {/* 分类侧栏 */}
      {categories.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <Space>
            <Button
              type={selectedCategory === null ? "primary" : "default"}
              onClick={() => setSelectedCategory(null)}
            >
              全部
            </Button>
            {categories.map((cat) => (
              <Button
                key={cat.id}
                type={selectedCategory === cat.id ? "primary" : "default"}
                onClick={() => setSelectedCategory(cat.id)}
              >
                {cat.name}
              </Button>
            ))}
          </Space>
        </div>
      )}

      {/* MCP 卡片列表 */}
      <Spin spinning={loading}>
        {filteredList.length === 0 ? (
          <Empty description="暂无 MCP" />
        ) : (
          <Row gutter={[16, 16]}>
            {filteredList.map((item) => (
              <Col key={item.item_id} xs={24} sm={12} md={8} lg={6}>
                <Card
                  hoverable
                  onClick={() => handleCardClick(item.item_id)}
                  style={{ height: 200 }}
                >
                  <Card.Meta
                    title={
                      <Space>
                        <Text strong>{item.name}</Text>
                      </Space>
                    }
                    description={
                      <>
                        <Text type="secondary" ellipsis>
                          {item.description || item.client_key}
                        </Text>
                        <div style={{ marginTop: 8 }}>
                          <Tag>调用 {item.call_count}</Tag>
                          <Tag>用户 {item.user_count}</Tag>
                        </div>
                      </>
                    }
                  />
                </Card>
              </Col>
            ))}
          </Row>
        )}
      </Spin>

      {/* 详情抽屉 */}
      <MCPDetailDrawer
        visible={drawerVisible}
        itemId={selectedItemId}
        sourceId={sourceId}
        bbkId={bbkId}
        userId={userId}
        userName={userName}
        isManager={isManager}
        onClose={() => setDrawerVisible(false)}
        onRefresh={handleRefresh}
      />

      {/* 上传弹窗 */}
      <MCPUploadModal
        visible={uploadModalVisible}
        sourceId={sourceId}
        userId={userId}
        userName={userName}
        categories={categories}
        onSuccess={handleUploadSuccess}
        onCancel={() => setUploadModalVisible(false)}
      />
    </div>
  );
}
```

- [ ] **Step 2: 提交**

```bash
git add console/src/pages/Market/MarketMCP.tsx
git commit -m "feat(market-mcp): implement market MCP tab with cards and drawer"
```

---

## Task 7: 实现市场 MCP 详情抽屉

**Files:**
- Create: `console/src/pages/Market/MCPDetailDrawer.tsx`

- [ ] **Step 1: 创建详情抽屉组件**

```typescript
// console/src/pages/Market/MCPDetailDrawer.tsx

import React, { useState, useEffect } from "react";
import {
  Drawer,
  Descriptions,
  Button,
  Space,
  Tag,
  Popconfirm,
  message,
  Modal,
  List,
  Spin,
  Typography,
  Divider,
  Table,
} from "antd";
import {
  DeleteOutlined,
  SendOutlined,
  ApiOutlined,
} from "@ant-design/icons";

import { marketMcpApi } from "../../api";
import type { MarketMCPDetail, MCPTestResult, DistributeRequest } from "../../api/types";
import { DistributeModal } from "./DistributeModal";

const { Text, Paragraph } = Typography;

interface MCPDetailDrawerProps {
  visible: boolean;
  itemId: string | null;
  sourceId: string;
  bbkId: string;
  userId: string;
  userName: string;
  isManager: boolean;
  onClose: () => void;
  onRefresh: () => void;
}

export function MCPDetailDrawer({
  visible,
  itemId,
  sourceId,
  bbkId,
  userId,
  userName,
  isManager,
  onClose,
  onRefresh,
}: MCPDetailDrawerProps) {
  const [loading, setLoading] = useState(false);
  const [detail, setDetail] = useState<MarketMCPDetail | null>(null);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<MCPTestResult | null>(null);
  const [testModalVisible, setTestModalVisible] = useState(false);
  const [distributeModalVisible, setDistributeModalVisible] = useState(false);

  useEffect(() => {
    if (visible && itemId) {
      loadDetail();
    }
  }, [visible, itemId]);

  const loadDetail = async () => {
    if (!itemId) return;
    setLoading(true);
    try {
      const data = await marketMcpApi.getDetail(sourceId, itemId, bbkId);
      setDetail(data);
    } catch (err) {
      message.error("加载详情失败");
    } finally {
      setLoading(false);
    }
  };

  const handleTest = async () => {
    if (!itemId) return;
    setTesting(true);
    try {
      const result = await marketMcpApi.test(sourceId, itemId);
      setTestResult(result);
      setTestModalVisible(true);
    } catch (err) {
      message.error("测试连接失败");
    } finally {
      setTesting(false);
    }
  };

  const handleDelete = async () => {
    if (!itemId) return;
    try {
      await marketMcpApi.delete(sourceId, itemId, userId, userName);
      message.success("已删除");
      onClose();
      onRefresh();
    } catch (err) {
      message.error("删除失败");
    }
  };

  const handleDistribute = async (req: DistributeRequest) => {
    if (!itemId) return;
    try {
      const result = await marketMcpApi.distribute(sourceId, itemId, userId, userName, req);
      message.success(`已分发 ${result.distributed_count} 个用户`);
      setDistributeModalVisible(false);
    } catch (err) {
      message.error("分发失败");
    }
  };

  return (
    <Drawer
      title={detail?.name || "MCP 详情"}
      placement="right"
      width={600}
      open={visible}
      onClose={onClose}
      loading={loading}
      extra={
        isManager && (
          <Space>
            <Button icon={<ApiOutlined />} loading={testing} onClick={handleTest}>
              测试连接
            </Button>
            <Button icon={<SendOutlined />} onClick={() => setDistributeModalVisible(true)}>
              分发
            </Button>
            <Popconfirm
              title="确定删除此 MCP？已分发的用户本地副本不会被删除。"
              onConfirm={handleDelete}
              okText="删除"
              cancelText="取消"
            >
              <Button danger icon={<DeleteOutlined />}>
                删除
              </Button>
            </Popconfirm>
          </Space>
        )
      }
    >
      {detail && (
        <>
          <Descriptions column={2} bordered size="small">
            <Descriptions.Item label="client_key">{detail.client_key}</Descriptions.Item>
            <Descriptions.Item label="创建者">{detail.creator_name}</Descriptions.Item>
            <Descriptions.Item label="描述" span={2}>
              {detail.description || "-"}
            </Descriptions.Item>
            <Descriptions.Item label="调用次数">{detail.call_count}</Descriptions.Item>
            <Descriptions.Item label="用户数">{detail.user_count}</Descriptions.Item>
            <Descriptions.Item label="传输类型">{detail.config.transport}</Descriptions.Item>
            <Descriptions.Item label="创建时间">{detail.created_at || "-"}</Descriptions.Item>

            {detail.config.transport === "stdio" && (
              <>
                <Descriptions.Item label="命令">{detail.config.command}</Descriptions.Item>
                <Descriptions.Item label="参数">
                  <Paragraph copyable>{detail.config.args.join(" ")}</Paragraph>
                </Descriptions.Item>
                <Descriptions.Item label="工作目录">{detail.config.cwd || "-"}</Descriptions.Item>
              </>
            )}

            {detail.config.transport !== "stdio" && (
              <Descriptions.Item label="URL">{detail.config.url}</Descriptions.Item>
            )}

            <Descriptions.Item label="环境变量" span={2}>
              <Paragraph copyable={{ text: JSON.stringify(detail.config.env, null, 2) }}>
                <pre style={{ margin: 0 }}>{JSON.stringify(detail.config.env, null, 2)}</pre>
              </Paragraph>
            </Descriptions.Item>

            <Descriptions.Item label="请求头" span={2}>
              <Paragraph copyable={{ text: JSON.stringify(detail.config.headers, null, 2) }}>
                <pre style={{ margin: 0 }}>{JSON.stringify(detail.config.headers, null, 2)}</pre>
              </Paragraph>
            </Descriptions.Item>
          </Descriptions>

          <Divider>用户统计</Divider>

          <Table
            dataSource={detail.user_stats}
            columns={[
              { title: "用户 ID", dataIndex: "user_id", key: "user_id" },
              { title: "用户名", dataIndex: "user_name", key: "user_name" },
              { title: "调用次数", dataIndex: "call_count", key: "call_count" },
            ]}
            rowKey="user_id"
            size="small"
            pagination={false}
          />
        </>
      )}

      {/* 测试结果弹窗 */}
      <Modal
        title="测试连接结果"
        open={testModalVisible}
        onCancel={() => setTestModalVisible(false)}
        footer={<Button onClick={() => setTestModalVisible(false)}>关闭</Button>}
        width={600}
      >
        {testResult?.success ? (
          <>
            <Text type="success">连接成功，可用工具：</Text>
            <List
              dataSource={testResult.tools}
              renderItem={(tool) => (
                <List.Item>
                  <List.Item.Meta title={tool.name} description={tool.description} />
                </List.Item>
              )}
            />
          </>
        ) : (
          <Text type="danger">连接失败：{testResult?.error}</Text>
        )}
      </Modal>

      {/* 分发弹窗 */}
      <DistributeModal
        visible={distributeModalVisible}
        onConfirm={handleDistribute}
        onCancel={() => setDistributeModalVisible(false)}
      />
    </Drawer>
  );
}
```

- [ ] **Step 2: 提交**

```bash
git add console/src/pages/Market/MCPDetailDrawer.tsx
git commit -m "feat(market-mcp): add MCP detail drawer with test, distribute and delete"
```

---

## Task 8: 实现 MCP 上传弹窗

**Files:**
- Create: `console/src/pages/Market/MCPUploadModal.tsx`

- [ ] **Step 1: 创建上传弹窗组件**

```typescript
// console/src/pages/Market/MCPUploadModal.tsx

import React, { useState } from "react";
import {
  Modal,
  Form,
  Upload,
  Input,
  Select,
  Button,
  Space,
  message,
  Checkbox,
} from "antd";
import { InboxOutlined } from "@ant-design/icons";

import { marketMcpApi } from "../../api";
import type { Category } from "../../api/types";

interface MCPUploadModalProps {
  visible: boolean;
  sourceId: string;
  userId: string;
  userName: string;
  categories: Category[];
  onSuccess: () => void;
  onCancel: () => void;
}

export function MCPUploadModal({
  visible,
  sourceId,
  userId,
  userName,
  categories,
  onSuccess,
  onCancel,
}: MCPUploadModalProps) {
  const [form] = Form.useForm();
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);

  const handleUpload = async (values: any) => {
    if (!file) {
      message.error("请上传 JSON 文件");
      return;
    }

    setLoading(true);
    try {
      const result = await marketMcpApi.upload(
        sourceId,
        userId,
        userName,
        file,
        values.name,
        values.description,
        values.category_id,
        values.bbk_ids
      );

      if (result.success) {
        message.success("上传成功");
        onSuccess();
      } else {
        message.error(result.error || "上传失败");
      }
    } catch (err) {
      message.error("上传失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      title="上传 MCP 连接器"
      open={visible}
      onCancel={onCancel}
      footer={null}
      width={500}
      destroyOnClose
    >
      <Form form={form} layout="vertical" onFinish={handleUpload}>
        <Form.Item label="上传文件">
          <Upload.Dragger
            accept=".json"
            beforeUpload={(f) => {
              setFile(f);
              return false;
            }}
            maxCount={1}
            onRemove={() => setFile(null)}
          >
            <p className="ant-upload-drag-icon">
              <InboxOutlined />
            </p>
            <p className="ant-upload-text">点击或拖拽 JSON 文件到此区域</p>
            <p className="ant-upload-hint">仅支持 .json 格式</p>
          </Upload.Dragger>
        </Form.Item>

        <Form.Item name="name" label="名称">
          <Input placeholder="可选，优先从文件解析" />
        </Form.Item>

        <Form.Item name="description" label="描述">
          <Input.TextArea rows={2} placeholder="可选" />
        </Form.Item>

        <Form.Item name="category_id" label="分类">
          <Select placeholder="可选" allowClear>
            {categories.map((cat) => (
              <Select.Option key={cat.id} value={cat.id}>
                {cat.name}
              </Select.Option>
            ))}
          </Select>
        </Form.Item>

        <Form.Item name="bbk_ids" label="可见范围">
          <Checkbox.Group>
            <Checkbox value="100">全部用户</Checkbox>
          </Checkbox.Group>
        </Form.Item>

        <Form.Item>
          <Space>
            <Button type="primary" htmlType="submit" loading={loading}>
              上传
            </Button>
            <Button onClick={onCancel}>取消</Button>
          </Space>
        </Form.Item>
      </Form>
    </Modal>
  );
}
```

- [ ] **Step 2: 提交**

```bash
git add console/src/pages/Market/MCPUploadModal.tsx
git commit -m "feat(market-mcp): add MCP upload modal"
```

---

## Task 9: 更新 Market 页面集成 MCP Tab

**Files:**
- Modify: `console/src/pages/Market/index.tsx`

- [ ] **Step 1: 更新 Market 页面支持 Skills/MCP 切换**

```typescript
// console/src/pages/Market/index.tsx

import { useState } from "react";
import { Tabs } from "antd";
import { MarketSkills } from "./MarketSkills";
import { MarketMCP } from "./MarketMCP";
import { useIframeStore } from "../../stores/iframeStore";
import { getUserId } from "../../utils/identity";
import { DEFAULT_SOURCE_ID, DEFAULT_BBK_ID } from "../../constants/identity";

export default function MarketPage() {
  const [activeTab, setActiveTab] = useState<"skills" | "mcp">("skills");
  const sourceId = useIframeStore((state) => state.source) || DEFAULT_SOURCE_ID;
  const bbkId = useIframeStore((state) => state.bbk) || DEFAULT_BBK_ID;
  const userId = getUserId();
  const userName = useIframeStore((state) => state.clawName) || "Unknown";
  const isManager = useIframeStore((state) => state.manager);

  return (
    <Tabs
      activeKey={activeTab}
      onChange={(key) => setActiveTab(key as "skills" | "mcp")}
      items={[
        {
          key: "skills",
          label: "技能市场",
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
          label: "MCP 市场",
          children: (
            <MarketMCP
              sourceId={sourceId}
              bbkId={bbkId}
              userId={userId}
              userName={userName}
              isManager={isManager}
            />
          ),
        },
      ]}
    />
  );
}
```

- [ ] **Step 2: 提交**

```bash
git add console/src/pages/Market/index.tsx
git commit -m "feat(market): add Skills/MCP tab switching"
```

---

## Task 10: 前端构建验证

- [ ] **Step 1: 运行前端格式化检查**

Run: `cd console && npm run lint`
Expected: 无错误

- [ ] **Step 2: 运行前端构建**

Run: `cd console && npm run build`
Expected: 构建成功

- [ ] **Step 3: 启动开发服务器测试**

Run: `cd console && npm run dev`
Expected: 页面可访问，路由正常

---

## 完成检查

| 检查项 | 状态 |
|--------|------|
| API 类型定义 | ✓ |
| API 模块 | ✓ |
| 我的 MCP 页面 | ✓ |
| MCP 详情面板 | ✓ |
| MCP 创建/编辑表单 | ✓ |
| 市场 MCP Tab | ✓ |
| 市场 MCP 详情抽屉 | ✓ |
| MCP 上传弹窗 | ✓ |
| Skills/MCP 切换 | ✓ |
| 前端构建 | ✓ |

---

## 整体项目完成检查

| 计划 | 状态 |
|------|------|
| 计划 A：本地 MCP 后端 | ✓ |
| 计划 B：市场 MCP 后端 | ✓ |
| 计划 C：前端 | ✓ |