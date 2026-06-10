import api from './api'

/**
 * 重新生成帧脚本+图片
 * @param {string} projectId - 项目 ID
 * @param {string} frameId - 帧 ID
 * @param {string} [instruction] - 可选的调整指令
 */
export async function regenerateFrame(projectId, frameId, instruction) {
  return api.post(`/v1/projects/${projectId}/frames/${frameId}/regenerate`, {
    instruction,
  })
}

/**
 * 仅重新生成帧图片
 * @param {string} projectId - 项目 ID
 * @param {string} frameId - 帧 ID
 * @param {string} [instruction] - 可选的图片调整指令
 */
export async function regenerateFrameImage(projectId, frameId, instruction) {
  return api.post(`/v1/projects/${projectId}/frames/${frameId}/regenerate-image`, {
    instruction,
  })
}

export async function regenerateFrameVideo(projectId, frameId, instruction) {
  return api.post(`/v1/projects/${projectId}/frames/${frameId}/regenerate-video`, {
    instruction,
  })
}

export async function retryFrame(projectId, frameId, instruction) {
  return api.post(`/v1/projects/${projectId}/frames/${frameId}/retry`, {
    instruction,
  })
}

export async function updateFrame(projectId, frameId, patch) {
  return api.patch(`/v1/projects/${projectId}/frames/${frameId}`, patch)
}
