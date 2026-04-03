# 会话处理状态标识设计文档

**日期**: 2026-04-03
**主题**: 会话处理过程中增加状态标识，包含动画、token 消耗、耗时和工具执行进度

## 背景与需求

参考 Claude Code 的交互体验，在会话处理过程中增加实时状态标识，让用户清晰感知当前处理进度。

### 需求要点

| 项目 | 决策 |
|------|------|
| 显示位置 | 输入框上方 |
| 处理状态 | 分段显示（等待中 → 处理中） |
| Token 消耗 | 节流更新（300ms），只计算最终展示文本 |
| 耗时 | 按秒计时 |
| 动画风格 | Claude Code 风格多点跳跃（复用 `Bubble.Spin`） |
| 工具进度 | 显示 "工具: X/Y 完成" |
| 交互 | 纯展示，无交互 |

## 设计决策

### 方案选择

选择 **方案 B：前端本地计算**，原因：
- 改动最小，只需修改前端
- 零后端改动，不影响现有流式响应逻辑
- 零额外网络请求
- 前端开销极小（一个计时器 + 字符估算）
- 节流保护，UI 更新频率可控

## 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                      Chat 页面                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│                    MessageList                                   │
│                    (消息列表区域)                                 │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────┐   │
│  │           ProcessingStatusBar                            │   │
│  │  [●●●] 处理中...  │  工具: 2/5 完成  │  1.2k tokens  │  12s  │   │
│  └─────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────┤
│                      Input                                       │
│                    (输入框区域)                                   │
└─────────────────────────────────────────────────────────────────┘
```

**状态栏位置**：在 `Input` 组件上方，`MessageList` 下方

## 组件结构

```
console/src/components/ProcessingStatusBar/
├── index.tsx              # 主组件
├── StatusIndicator.tsx    # 状态指示器（闪烁点 + 文字）
├── ToolProgress.tsx       # 工具执行进度
├── TokenCounter.tsx       # Token 计数器
├── ElapsedTimer.tsx       # 耗时计时器
└── style.ts               # 样式
```

## 状态管理

### 新增状态定义

```typescript
// console/src/chat/AgentScopeRuntimeWebUI/core/Context/ChatAnywhereInputContext.tsx

interface ToolProgress {
  total: number;       // 总工具调用数
  completed: number;   // 已完成数
  inProgress: number;  // 进行中数
  failed: number;      // 失败数
}

interface ProcessingState {
  status: 'idle' | 'waiting' | 'processing';
  startTime: number | null;
  tokenCount: number;
  toolProgress: ToolProgress | null;
}

interface IAgentScopeRuntimeWebUIInputContext {
  // ... 现有字段
  processing: ProcessingState;
  setProcessing: (state: Partial<ProcessingState>) => void;
}

const defaultProcessing: ProcessingState = {
  status: 'idle',
  startTime: null,
  tokenCount: 0,
  toolProgress: null,
};
```

### 状态流转

```
用户发送消息
    ↓
setProcessing({ status: 'waiting', startTime: Date.now(), tokenCount: 0, toolProgress: null })
    ↓
收到第一个 SSE 内容事件
    ↓
setProcessing({ status: 'processing' })
    ↓
持续更新 tokenCount 和 toolProgress（节流）
    ↓
收到完成事件
    ↓
setProcessing({ status: 'idle', startTime: null, tokenCount: 0, toolProgress: null })
```

### 状态显示逻辑

| 阶段 | 状态文案 | 工具进度 |
|------|----------|----------|
| 等待 | 等待中... | 隐藏 |
| 处理中（无工具调用） | 处理中... | 隐藏 |
| 处理中（有工具调用） | 处理中... | 显示 "工具: X/Y 完成" |

## 核心实现

### Token 计算

只计算最终展示给用户的文本，排除工具调用数据：

```typescript
function extractDisplayText(output: IAgentScopeRuntimeMessage[]): string {
  let text = '';

  for (const msg of output) {
    // 只提取 MESSAGE 类型的文本内容
    if (msg.type === AgentScopeRuntimeMessageType.MESSAGE) {
      for (const content of msg.content || []) {
        if (content.type === AgentScopeRuntimeContentType.TEXT) {
          text += (content as ITextContent).text || '';
        }
      }
    }
  }

  return text;
}

// 简单估算：字符数 / 4（中英文混合的平均比例）
function estimateTokens(text: string): number {
  return Math.ceil(text.length / 4);
}
```

### 工具进度计算

```typescript
function calculateToolProgress(output: IAgentScopeRuntimeMessage[]): ToolProgress | null {
  const toolMessages = output.filter(msg =>
    [AgentScopeRuntimeMessageType.FUNCTION_CALL,
     AgentScopeRuntimeMessageType.PLUGIN_CALL,
     AgentScopeRuntimeMessageType.MCP_CALL].includes(msg.type)
  );

  if (toolMessages.length === 0) return null;

  return {
    total: toolMessages.length,
    completed: toolMessages.filter(m => m.status === AgentScopeRuntimeRunStatus.Completed).length,
    inProgress: toolMessages.filter(m => m.status === AgentScopeRuntimeRunStatus.InProgress).length,
    failed: toolMessages.filter(m => m.status === AgentScopeRuntimeRunStatus.Failed).length,
  };
}
```

### 节流更新

Token 和工具进度使用 300ms 节流更新，避免高频重渲染：

```typescript
const TokenCounter: React.FC<{ count: number }> = ({ count }) => {
  const [displayCount, setDisplayCount] = useState(0);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDisplayCount(count);
    }, 300); // 300ms 节流

    return () => clearTimeout(timer);
  }, [count]);

  return <span>{formatToken(displayCount)}</span>;
};

function formatToken(count: number): string {
  if (count >= 1000) return `${(count / 1000).toFixed(1)}k`;
  return count.toString();
}
```

### 耗时计时器

按秒计时：

```typescript
const ElapsedTimer: React.FC<{ startTime: number | null }> = ({ startTime }) => {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!startTime) return;

    setElapsed(0); // 重置

    const timer = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);

    return () => clearInterval(timer);
  }, [startTime]);

  return <span>{elapsed}s</span>;
};
```

## 集成点

### 1. Context 扩展

修改 `ChatAnywhereInputContext`，添加处理状态：

**文件**: `console/src/chat/AgentScopeRuntimeWebUI/core/Context/ChatAnywhereInputContext.tsx`

- 添加 `ProcessingState` 接口
- 添加 `processing` 和 `setProcessing` 到 Context

### 2. 触发时机

| 时机 | 文件 | 操作 |
|------|------|------|
| 发送消息 | `useChatMessageHandler.tsx` | `setProcessing({ status: 'waiting', startTime: Date.now() })` |
| 收到首个内容 | `useChatRequest.tsx` | `setProcessing({ status: 'processing' })` |
| 累计 token 和进度 | `useChatRequest.tsx` | 节流更新 `tokenCount` 和 `toolProgress` |
| 处理完成 | `useChatRequest.tsx` | `setProcessing({ status: 'idle' })` |

### 3. 渲染位置

**文件**: `console/src/chat/AgentScopeRuntimeWebUI/core/Chat/index.tsx`

```typescript
<div className={prefixCls}>
  <MessageList onSubmit={handleSubmit} />

  {/* 新增：处理状态栏 */}
  <ProcessingStatusBar />

  <Input onSubmit={handleSubmit} />
</div>
```

## 样式设计

```typescript
// console/src/components/ProcessingStatusBar/style.ts

import { createGlobalStyle } from 'antd-style';

export default createGlobalStyle`
  .${(p) => p.prefixCls}-processing-status-bar {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 8px 16px;
    background: ${(p) => p.theme.colorBgContainer};
    border-top: 1px solid ${(p) => p.theme.colorBorderSecondary};
    font-size: 13px;
    color: ${(p) => p.theme.colorTextSecondary};
  }

  .${(p) => p.prefixCls}-processing-status-bar-status {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .${(p) => p.prefixCls}-processing-status-bar-divider {
    width: 1px;
    height: 12px;
    background: ${(p) => p.theme.colorBorderSecondary};
  }

  .${(p) => p.prefixCls}-processing-status-bar-tool-progress {
    .failed {
      color: ${(p) => p.theme.colorError};
    }
  }
`;
```

## 文件变更清单

### 新增文件

| 文件路径 | 描述 |
|----------|------|
| `console/src/components/ProcessingStatusBar/index.tsx` | 主组件 |
| `console/src/components/ProcessingStatusBar/StatusIndicator.tsx` | 状态指示器 |
| `console/src/components/ProcessingStatusBar/ToolProgress.tsx` | 工具进度显示 |
| `console/src/components/ProcessingStatusBar/TokenCounter.tsx` | Token 计数器 |
| `console/src/components/ProcessingStatusBar/ElapsedTimer.tsx` | 耗时计时器 |
| `console/src/components/ProcessingStatusBar/style.ts` | 样式文件 |

### 修改文件

| 文件路径 | 变更内容 |
|----------|----------|
| `console/src/chat/AgentScopeRuntimeWebUI/core/Context/ChatAnywhereInputContext.tsx` | 添加 `ProcessingState` 状态定义和 Context 字段 |
| `console/src/chat/AgentScopeRuntimeWebUI/core/Chat/hooks/useChatMessageHandler.tsx` | 发送消息时设置 `waiting` 状态 |
| `console/src/chat/AgentScopeRuntimeWebUI/core/Chat/hooks/useChatRequest.tsx` | 流处理中更新状态、token、进度；完成时重置状态 |
| `console/src/chat/AgentScopeRuntimeWebUI/core/Chat/index.tsx` | 添加 `ProcessingStatusBar` 组件渲染 |

## 测试要点

### 功能测试

1. **状态流转**：
   - 发送消息后立即显示 "等待中..."
   - 收到首个 SSE 事件后切换为 "处理中..."
   - 完成后状态栏消失

2. **Token 显示**：
   - 只计算最终展示文本的 token
   - 不计入工具调用参数和返回数据
   - 显示值节流更新，无快速闪烁

3. **耗时显示**：
   - 从发送消息开始计时
   - 每秒更新一次
   - 完成后停止计时

4. **工具进度**：
   - 无工具调用时不显示进度
   - 有工具调用时显示 "工具: X/Y 完成"
   - 失败时显示失败数量（红色）

### 边界情况

| 场景 | 预期行为 |
|------|----------|
| 用户中断请求 | 状态栏消失，显示中断状态 |
| 请求失败 | 状态栏消失，显示错误信息 |
| 快速连续发送 | 新请求覆盖旧状态 |
| 空响应 | 状态栏正常消失 |
