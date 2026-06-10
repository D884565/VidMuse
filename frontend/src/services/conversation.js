import api from './api'

/**
 * 获取项目对话历史
 * @param {string} projectId - 项目 ID
 * @returns {Promise<Array<{id, role, content, frame_id, created_at}>>}
 */
export async function getConversations(projectId) {
  return api.get(`/v1/projects/${projectId}/conversations`)
}
