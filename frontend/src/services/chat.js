import api from './api'

// 发送聊天消息（非流式，保留向后兼容）
export async function sendChatMessage(projectId, content, frameId = null) {
  return api.post(`/v1/projects/${projectId}/chat`, {
    content,
    frame_id: frameId,
  })
}

// 发送聊天消息（SSE 流式）
export async function sendChatMessageStream(projectId, content, frameId, callbacks) {
  return sendSseChat(`/api/generate/v1/projects/${projectId}/chat/stream`, { content, frame_id: frameId }, callbacks)
}

export async function sendEntryChatMessageStream(content, callbacks) {
  return sendSseChat('/api/generate/v1/chat/entry/stream', { content }, callbacks)
}

async function sendSseChat(url, payload, callbacks) {
  const { onStart, onToken, onBlocks, onDone, onError, onThinking } = callbacks
  const token = localStorage.getItem('token')

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(payload),
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() // 保留不完整的行

      let eventType = ''
      for (const line of lines) {
        if (line.startsWith('event: ')) {
          eventType = line.slice(7).trim()
        } else if (line.startsWith('data: ')) {
          const jsonStr = line.slice(6)
          try {
            const data = JSON.parse(jsonStr)
            if (eventType === 'thinking') onThinking?.(data)
            else if (eventType === 'start') onStart?.(data)
            else if (eventType === 'token') onToken?.(data)
            else if (eventType === 'blocks') onBlocks?.(data)
            else if (eventType === 'done') onDone?.(data)
            else if (eventType === 'error') {
              onError?.(new Error(data.message || data.error || '请求失败'))
              return
            }
          } catch {
            // 忽略解析错误
          }
        }
      }
    }
  } catch (err) {
    onError?.(err)
  }
}
