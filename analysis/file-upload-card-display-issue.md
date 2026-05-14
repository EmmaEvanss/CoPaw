# 首页附件上传功能实现

## 问题描述

欢迎页（WelcomeCenterLayout）需要支持附件上传功能，但上传后出现**两个输入框**：
1. 欢迎页自带的输入框
2. 底部 Chat/Input 组件的输入框（显示附件预览卡片）

## 解决方案

采用**双输入框独立架构**：WelcomeCenterLayout 和底部 Input 完全解耦，各自管理自己的文件状态。

### 架构设计

```
欢迎页（WelcomeCenterLayout）
  ├─ 独立的输入框和发送逻辑
  ├─ 独立的 fileList 状态管理
  ├─ 直接调用 chatApi.uploadFile 上传
  ├─ Attachments 组件渲染预览卡片（在输入框上方）
  └─ onSubmit 时携带 { query, fileList }

历史会话（底部 Input）
  ├─ 通过 useAttachments hook 管理
  ├─ customRequest 处理文件上传
  └─ Sender.Header 渲染附件列表

关键决策：
  ✅ WelcomeCenterLayout 不 dispatch pasteFile 事件
  ✅ 两个系统完全解耦，互不干扰
  ✅ 底部 Input 仅在 hasMessages=true 时显示
```

## 技术实现

### 1. WelcomeCenterLayout 修改

#### 文件位置
`console/src/components/agentscope-chat/WelcomeCenterLayout/index.tsx`

#### 完整实现代码


```typescript
import { message } from "antd";
import { chatApi } from "@/api/modules/chat";
import { useTranslation } from 'react-i18next';
```


```typescript
interface WelcomeCenterLayoutProps {
  greeting?: string;
  // 支持 fileList 参数，与底部 Input 保持一致
  onSubmit: (data: { query: string; fileList?: any[] }) => void;
}
```


```typescript
const [fileList, setFileList] = useState<UploadFile[]>([]);
```


```typescript
const handleBeforeUpload = useCallback((file: File) => {
  const uid = `welcome-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const uploadFile: UploadFile = {
    uid,
    name: file.name,
    size: file.size,
    type: file.type,
    status: "uploading",
    percent: 0,
    originFileObj: file as any,
  };

  setFileList((prev) => [...prev, uploadFile]);

  // 生成图片缩略图
  if (file.type.startsWith("image/")) {
    const reader = new FileReader();
    reader.onload = (e) => {
      const dataUrl = e.target?.result;
      if (typeof dataUrl === "string") {
        setFileList((prev) =>
          prev.map((f) =>
            f.uid === uid ? { ...f, thumbUrl: dataUrl } : f,
          ),
        );
      }
    };
    reader.readAsDataURL(file);
  }

  // 真正调用 API 上传文件
  chatApi
    .uploadFile(file)
    .then((res) => {
      setFileList((prev) =>
        prev.map((f) =>
          f.uid === uid
            ? {
                ...f,
                status: "done" as const,
                percent: 100,
                response: { url: chatApi.filePreviewUrl(res.url) },
              }
            : f,
        ),
      );
    })
    .catch((error) => {
      console.error("File upload failed:", error);
      message.error(t("chat.attachments.uploadFailed"));
      setFileList((prev) => prev.filter((f) => f.uid !== uid));
    });

  return false; // 阻止默认上传行为
}, [t]);
```


```typescript
const handleSend = useCallback(() => {
  const trimmed = inputValue.trim();
  if (!trimmed) return;

  // 过滤出已成功上传的文件
  const uploadedFiles = fileList.filter((f) => f.response?.url);

  // 提交时包含文件列表
  onSubmit({ query: trimmed, fileList: uploadedFiles });
  setInputValue("");
  setFileList([]);
}, [inputValue, fileList, onSubmit]);
```


```tsx
<div className="welcome-input-card">
  {/* 附件预览区域 */}
  {fileList.length > 0 && (
    <div style={{ marginBottom: 8 }}>
      <Attachments
        items={fileList}
        onChange={(info) => setFileList(info.fileList)}
      />
    </div>
  )}

  {/* 输入框 */}
  <Input.TextArea
    value={inputValue}
    onChange={(e) => setInputValue(e.target.value)}
    onKeyDown={handleKeyDown}
    placeholder={randomPlaceholder}
    autoSize={{ minRows: 1, maxRows: 5 }}
    bordered={false}
  />

  {/* 操作栏：上传按钮 + 发送按钮 */}
  <div className="welcome-input-actions">
    <Upload beforeUpload={handleBeforeUpload}>
      <IconButton icon={<SparkAttachmentLine />} bordered={false} />
    </Upload>
    <button onClick={handleSend} disabled={!inputValue.trim()}>
      <img src={sendIcon} alt="发送" width={28} height={28} />
    </button>
  </div>
</div>
```

### 2. Input/index.tsx 清理

#### 文件位置
`console/src/components/agentscope-chat/AgentScopeRuntimeWebUI/core/Chat/Input/index.tsx`

#### 修改内容

删除无用的 pasteFile 事件监听器（原第 60-70 行），替换为注释说明。





### 3. Chat/index.tsx 优化

#### 文件位置
`console/src/components/agentscope-chat/AgentScopeRuntimeWebUI/core/Chat/index.tsx`

#### 修改内容

显式控制 Input 组件的显示，仅在历史会话时可见。


## 数据流

## 关键技术点

### 1. 文件上传 API 复用

WelcomeCenterLayout 直接使用 `chatApi.uploadFile`，与底部 Input 的 `customRequest` 使用相同的后端接口：
- 接口：`POST /console/upload`
- 返回：`{ url: string }`
- 预览 URL：`chatApi.filePreviewUrl(url)` 添加 token

### 2. TypeScript 类型一致性

WelcomeCenterLayout 的 `onSubmit` 类型与父组件保持一致：
```typescript
// IAgentScopeRuntimeWebUIWelcomeOptions.render
onSubmit: (data: { query: string; fileList?: any[] }) => void
```

### 3. 附件过滤逻辑

发送消息时只包含已成功上传的文件：
```typescript
const uploadedFiles = fileList.filter((f) => f.response?.url);
```

### 4. 事件通信解耦

- WelcomeCenterLayout 不 dispatch `pasteFile` 事件
- 两个系统完全独立，避免状态同步问题
- 拖拽上传仍通过 `pasteFile` 事件传递给底部 Input

## 测试场景

### 场景 1：欢迎页上传并发送
1. 打开应用，进入欢迎页
2. 点击上传按钮，选择文件
3. 预期：附件预览卡片显示在欢迎页输入框上方
4. 预期：底部没有显示 Input 组件
5. 输入文本，点击发送
6. 预期：消息和附件一起发送到后端
7. 预期：进入历史会话，底部 Input 显示

### 场景 2：历史会话上传附件
1. 已有聊天记录
2. 拖拽文件到聊天区域
3. 预期：底部 Input 显示附件预览
4. 输入文本，点击发送
5. 预期：消息和附件一起发送

### 场景 3：欢迎页多次上传
1. 上传第一个文件
2. 上传第二个文件
3. 预期：两个附件都显示在欢迎页
4. 删除其中一个附件
5. 预期：只剩一个附件
6. 发送消息
7. 预期：只发送剩余的附件

### 场景 4：上传失败处理
1. 上传一个大文件（超过限制）
2. 预期：显示错误提示
3. 预期：文件从列表中移除
4. 预期：不影响其他正常上传的文件

## 注意事项

### 1. useAttachments.tsx 使用受控模式

当前使用 antd Upload 的受控模式：
```typescript
<Upload
  fileList={fileList}
  onChange={(info) => setFileList(info.fileList)}
  {...rest}
/>
```

如遇到 Upload onChange 不触发或附件显示异常，可考虑改用 `beforeUpload` + `return false` 方式。

### 2. 并发上传

每个文件独立调用 `chatApi.uploadFile`，无并发限制。如需优化，可添加上传队列。

## 相关文件

### 修改的文件
1. `console/src/components/agentscope-chat/WelcomeCenterLayout/index.tsx` - 新增文件上传逻辑
2. `console/src/components/agentscope-chat/AgentScopeRuntimeWebUI/core/Chat/Input/index.tsx` - 删除无用事件监听器
3. `console/src/components/agentscope-chat/AgentScopeRuntimeWebUI/core/Chat/index.tsx` - 显式控制 Input 显示

### 依赖的文件
1. `console/src/api/modules/chat.ts` - 提供 `uploadFile` 和 `filePreviewUrl` 方法
2. `console/src/components/agentscope-chat/AgentScopeRuntimeWebUI/core/Chat/Input/useAttachments.tsx` - 底部 Input 附件管理

## 总结

### 核心改进
1. **单一输入源**：欢迎页和历史会话各有独立的输入框，不会同时显示
2. **状态隔离**：两个系统完全解耦，互不干扰
3. **API 复用**：WelcomeCenterLayout 使用相同的上传 API
4. **类型安全**：TypeScript 类型定义一致
5. **代码简洁**：删除了无用的事件监听器

### 架构优势
- **清晰的责任划分**：欢迎页负责欢迎态交互，底部 Input 负责历史会话
- **易于维护**：两个系统独立，修改一个不会影响另一个
- **可扩展性**：未来可以轻松添加更多输入入口
