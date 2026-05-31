import api from './api'

// 创建新项目
export async function createProject(data) {
  return api.post('/generate/v1/projects', data)
}

export async function generateProjectScript(projectId, options = {}) {
  return api.post(`/generate/v1/projects/${projectId}/script/generate`, null, {
    params: { force: !!options.force },
  })
}

export async function renderProject(projectId) {
  return api.post(`/generate/v1/projects/${projectId}/render`)
}

export async function confirmWorkflowStage(projectId, stage) {
  return api.post(`/generate/v1/projects/${projectId}/workflow/confirm`, { stage })
}

export async function advanceWorkflowStage(projectId, confirmedStage) {
  return api.post(`/generate/v1/projects/${projectId}/workflow/advance`, {
    confirmed_stage: confirmedStage,
  })
}

export async function getGenerationTask(taskId) {
  return api.get(`/generate/v1/tasks/${taskId}`)
}

export async function getGenerationTaskSteps(taskId) {
  return api.get(`/generate/v1/tasks/${taskId}/steps`)
}

// 获取项目详情（轮询用）
export async function getProjectDetail(projectId) {
  return api.get(`/generate/v1/projects/${projectId}`)
}

/**
 * 获取项目列表
 * @param {Object} params - 查询参数
 * @param {number} [params.status] - 状态筛选 (0=待生成, 1=生成中, 2=已完成, 3=失败)
 * @param {string} [params.keyword] - 关键词搜索
 * @param {string} [params.start_date] - 开始日期 YYYY-MM-DD
 * @param {string} [params.end_date] - 结束日期 YYYY-MM-DD
 * @param {number} [params.page] - 页码
 * @param {number} [params.page_size] - 每页数量
 */
export async function getProjects(params = {}) {
  return api.get('/generate/v1/projects', { params })
}

// 更新项目
export async function updateProject(projectId, data) {
  return api.put(`/generate/v1/projects/${projectId}`, data)
}

// 删除项目
export async function deleteProject(projectId) {
  return api.delete(`/generate/v1/projects/${projectId}`)
}

export async function getProjectScripts(projectId) {
  return api.get(`/generate/v1/projects/${projectId}/scripts`)
}

/**
 * 直接下载项目成片视频到本地（blob 方式），不创建异步任务。
 */
export async function downloadProjectVideo(projectId) {
  const response = await api.get(`/generate/v1/projects/${projectId}/export/download`, {
    responseType: 'blob',
  })
  // 从 content-disposition 取文件名
  const disposition = response.headers?.['content-disposition'] || ''
  const match = disposition.match(/filename="?([^";\n]+)"?/)
  const filename = match ? match[1] : `project_${projectId}.mp4`
  // 触发浏览器下载
  const blob = response.data instanceof Blob ? response.data : new Blob([response.data])
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
  return { filename }
}

export async function bindProjectAsset(projectId, payload) {
  return api.post(`/generate/v1/projects/${projectId}/assets`, payload)
}
