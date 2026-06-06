import api from './api'

export async function createProject(data) {
  return api.post('/v1/projects', data)
}

export async function generateProjectScript(projectId, options = {}) {
  return api.post(`/v1/projects/${projectId}/script/generate`, null, {
    params: { force: !!options.force },
  })
}

export async function renderProject(projectId) {
  return api.post(`/v1/projects/${projectId}/render`)
}

export async function confirmWorkflowStage(projectId, stage) {
  return api.post(`/v1/projects/${projectId}/workflow/confirm`, { stage })
}

export async function advanceWorkflowStage(projectId, confirmedStage) {
  return api.post(`/v1/projects/${projectId}/workflow/advance`, {
    confirmed_stage: confirmedStage,
  })
}

export async function getGenerationTask(taskId) {
  return api.get(`/v1/tasks/${taskId}`)
}

export async function getGenerationTaskSteps(taskId) {
  return api.get(`/v1/tasks/${taskId}/steps`)
}

export async function getProjectDetail(projectId) {
  return api.get(`/generate/v1/projects/${projectId}`)
}

export async function getProjects(params = {}) {
  return api.get('/generate/v1/projects', { params })
}

export async function updateProject(projectId, data) {
  return api.put(`/generate/v1/projects/${projectId}`, data)
}

export async function deleteProject(projectId) {
  return api.delete(`/generate/v1/projects/${projectId}`)
}

export async function getProjectScripts(projectId) {
  return api.get(`/generate/v1/projects/${projectId}/scripts`)
}

export async function getProjectScript(projectId, scriptId) {
  return api.get(`/generate/v1/projects/${projectId}/scripts/${scriptId}`)
}

export async function downloadProjectVideo(projectId) {
  const response = await api.get(`/generate/v1/projects/${projectId}/export/download`, {
    responseType: 'blob',
  })

  const contentType = response.headers?.['content-type'] || ''
  if (contentType.includes('application/json')) {
    const errorText = await response.data.text()
    const errorPayload = JSON.parse(errorText)
    throw new Error(errorPayload.message || '导出失败')
  }

  const disposition = response.headers?.['content-disposition'] || ''
  const utf8Match = disposition.match(/filename\*=UTF-8''([^;\n]+)/i)
  const asciiMatch = disposition.match(/filename="?([^";\n]+)"?/)
  const filename = utf8Match
    ? decodeURIComponent(utf8Match[1])
    : asciiMatch
      ? asciiMatch[1]
      : `project_${projectId}.mp4`

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

export async function confirmPendingAction(projectId, pendingActionId) {
  return api.post(`/generate/v1/projects/${projectId}/pending-actions/${pendingActionId}/confirm`)
}

export async function cancelPendingAction(projectId, pendingActionId) {
  return api.post(`/generate/v1/projects/${projectId}/pending-actions/${pendingActionId}/cancel`)
}
