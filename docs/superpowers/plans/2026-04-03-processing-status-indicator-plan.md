# 会话处理状态标识实现计划

**设计文档**: [2026-04-03-processing-status-indicator-design.md](../specs/2026-04-03-processing-status-indicator-design.md)
**创建日期**: 2026-04-03

## 实现步骤

### 步骤 1: 扩展 Context 状态定义

**文件**: `console/src/chat/AgentScopeRuntimeWebUI/core/Context/ChatAnywhereInputContext.tsx`

**任务**:
- [ ] 添加 `ToolProgress` 接口定义
- [ ] 添加 `ProcessingState` 接口定义
- [ ] 在 `IAgentScopeRuntimeWebUIInputContext` 中添加 `processing` 和 `setProcessing` 字段
- [ ] 在 Context Provider 中初始化默认状态

**依赖**: 无

---

### 步骤 2: 创建 ProcessingStatusBar 组件

**文件**: `console/src/components/ProcessingStatusBar/` (新建目录)

**任务**:
- [ ] 创建 `index.tsx` 主组件
- [ ] 创建 `StatusIndicator.tsx` 状态指示器（复用 Bubble.Spin）
- [ ] 创建 `ToolProgress.tsx` 工具进度显示
- [ ] 创建 `TokenCounter.tsx` Token 计数器（含节流逻辑）
- [ ] 创建 `ElapsedTimer.tsx` 耗时计时器
- [ ] 创建 `style.ts` 样式文件

**依赖**: 步骤 1

---

### 步骤 3: 修改 useChatMessageHandler 触发等待状态

**文件**: `console/src/chat/AgentScopeRuntimeWebUI/core/Chat/hooks/useChatMessageHandler.tsx`

**任务**:
- [ ] 在发送消息时调用 `setProcessing({ status: 'waiting', startTime: Date.now() })`
- [ ] 确保状态重置逻辑正确

**依赖**: 步骤 1

---

### 步骤 4: 修改 useChatRequest 实现状态更新

**文件**: `console/src/chat/AgentScopeRuntimeWebUI/core/Chat/hooks/useChatRequest.tsx`

**任务**:
- [ ] 添加 `extractDisplayText` 函数提取展示文本
- [ ] 添加 `estimateTokens` 函数估算 token
- [ ] 添加 `calculateToolProgress` 函数计算工具进度
- [ ] 在流处理中判断首个内容事件，切换为 `processing` 状态
- [ ] 在流处理中累计 token 和工具进度（含节流）
- [ ] 在完成/失败时重置状态为 `idle`
- [ ] 处理中断请求的状态重置

**依赖**: 步骤 1, 步骤 2

---

### 步骤 5: 集成 ProcessingStatusBar 到 Chat 页面

**文件**: `console/src/chat/AgentScopeRuntimeWebUI/core/Chat/index.tsx`

**任务**:
- [ ] 导入 `ProcessingStatusBar` 组件
- [ ] 在 `MessageList` 和 `Input` 之间渲染 `ProcessingStatusBar`

**依赖**: 步骤 2

---

### 步骤 6: 测试验证

**任务**:
- [ ] 验证状态流转：等待中 → 处理中 → 消失
- [ ] 验证 token 显示只计算展示文本
- [ ] 验证耗时按秒计时
- [ ] 验证工具进度显示正确
- [ ] 验证中断请求时状态正确重置
- [ ] 验证请求失败时状态正确处理

**依赖**: 步骤 1-5

---

## 文件变更总览

### 新增文件 (6 个)

| 文件路径 | 描述 |
|----------|------|
| `console/src/components/ProcessingStatusBar/index.tsx` | 主组件 |
| `console/src/components/ProcessingStatusBar/StatusIndicator.tsx` | 状态指示器 |
| `console/src/components/ProcessingStatusBar/ToolProgress.tsx` | 工具进度 |
| `console/src/components/ProcessingStatusBar/TokenCounter.tsx` | Token 计数器 |
| `console/src/components/ProcessingStatusBar/ElapsedTimer.tsx` | 耗时计时器 |
| `console/src/components/ProcessingStatusBar/style.ts` | 样式 |

### 修改文件 (4 个)

| 文件路径 | 变更内容 |
|----------|----------|
| `console/src/chat/AgentScopeRuntimeWebUI/core/Context/ChatAnywhereInputContext.tsx` | 添加状态定义 |
| `console/src/chat/AgentScopeRuntimeWebUI/core/Chat/hooks/useChatMessageHandler.tsx` | 触发等待状态 |
| `console/src/chat/AgentScopeRuntimeWebUI/core/Chat/hooks/useChatRequest.tsx` | 状态更新逻辑 |
| `console/src/chat/AgentScopeRuntimeWebUI/core/Chat/index.tsx` | 渲染状态栏 |

## 风险与注意事项

1. **性能**: token 计算在流处理中执行，需确保节流生效，避免高频更新
2. **状态同步**: 确保中断和错误场景下状态正确重置，避免状态残留
3. **国际化**: 状态文案后续可扩展为多语言支持
