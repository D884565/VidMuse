import api from './api'

// 发送聊天消息
export async function sendChatMessage(projectId, content, frameId = null) {
  return api.post(`/generate/v1/projects/${projectId}/chat`, {
    content,
    frame_id: frameId,
  })
}
