import api from './api'

// 创建新项目
export async function createProject(data) {
  return api.post('/generate/v1/projects', data)
}

// 获取项目详情
export async function getProjectDetail(projectId) {
  return api.get(`/generate/v1/projects/${projectId}`)
}
