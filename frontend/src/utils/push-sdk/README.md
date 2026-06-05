# 推送SDK使用文档

## 安装
直接导入即可使用：

```javascript
import { PushClient } from '@/utils/push-sdk'
```

## 快速开始

### 1. 初始化客户端
```javascript
const pushClient = new PushClient({
  wsUrl: `${import.meta.env.VITE_API_BASE_URL.replace('http', 'ws')}/v1/ws/connect`,
  token: localStorage.getItem('token'),
  autoReconnect: true,  // 自动重连
  maxReconnectAttempts: 10,  // 最大重连次数
  reconnectInterval: 3000,  // 重连间隔（毫秒）
  heartbeatInterval: 30000,  // 心跳间隔（毫秒）
})
```

### 2. 建立连接
```javascript
pushClient.connect()
```

### 3. 监听消息
```javascript
// 监听所有消息
pushClient.onMessage((message) => {
  console.log('收到消息:', message)
})

// 监听特定类型的消息
pushClient.onMessageType('agent_progress', (message) => {
  // 处理Agent进度消息
  console.log('Agent进度:', message.content)
})

pushClient.onMessageType('task_status', (message) => {
  // 处理任务状态消息
  console.log('任务状态更新:', message.content)
})

pushClient.onMessageType('system_notification', (message) => {
  // 处理系统通知
  console.log('系统通知:', message.title, message.content)
})
```

### 4. 事件监听
```javascript
// 连接成功
pushClient.onConnect(() => {
  console.log('连接成功')
})

// 连接断开
pushClient.onDisconnect(({ code, reason }) => {
  console.log('连接断开:', code, reason)
})

// 重连尝试
pushClient.onReconnectAttempt((attempt) => {
  console.log(`正在尝试重连，第${attempt}次...`)
})

// 重连成功
pushClient.onReconnectSuccess(() => {
  console.log('重连成功')
})

// 错误
pushClient.onError((error) => {
  console.error('连接错误:', error)
})
```

### 5. API方法

#### 获取历史消息
```javascript
const messages = await pushClient.getHistoryMessages({
  page: 1,
  page_size: 20,
  message_type: 'agent_progress',
  is_read: false
})
```

#### 标记消息为已读
```javascript
await pushClient.markMessagesAsRead(['message_id_1', 'message_id_2'])
```

#### 获取未读消息数量
```javascript
const result = await pushClient.getUnreadCount()
console.log('未读消息数量:', result.data.unread_count)
```

### 6. 断开连接
```javascript
pushClient.disconnect()
```

## 消息格式说明
```javascript
{
  message_id: "uuid",          // 消息唯一ID
  message_type: "agent_progress",  // 消息类型
  title: "AI思考中",           // 消息标题
  content: {},                 // 消息内容（任意JSON结构）
  level: "info",               // 消息级别：info/success/warning/error
  trace_id: "abc123",          // 关联的trace_id（可选）
  extra: {},                   // 扩展字段（可选）
  created_at: "2026-06-05T12:00:00.000Z"  // 创建时间
}
```