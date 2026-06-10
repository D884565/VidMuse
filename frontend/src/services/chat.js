import api from './api'

/** 发送聊天消息到指定项目 */
export async function sendChatMessage(projectId, payload, frameId = null) {
  const requestPayload = typeof payload === 'string'
    ? { content: payload, frame_id: frameId }
    : { ...payload, frame_id: payload?.frame_id ?? frameId }

  return api.post(`/v1/projects/${projectId}/chat`, requestPayload)
}

export async function analyzeChatReference(file) {
  const formData = new FormData()
  formData.append('file', file)
  return api.post('/v1/chat/analyze-reference', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export async function sendChatMessageStream(projectId, payload, callbacks) {
  return sendSseChat(`/api/v1/projects/${projectId}/chat/stream`, payload, callbacks)
}

export async function sendEntryChatMessageStream(payload, callbacks) {
  return sendSseChat('/api/v1/chat/entry/stream', payload, callbacks)
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
      buffer = lines.pop()

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
            // Ignore malformed SSE payloads.
          }
        }
      }
    }
  } catch (err) {
    onError?.(err)
  }
}
