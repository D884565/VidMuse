import api from './api'

/**
 * 重新生成帧脚本+图片
 * @param {string} projectId - 项目 ID
 * @param {string} frameId - 帧 ID
 * @param {string} [instruction] - 可选的调整指令
 */
export async function regenerateFrame(projectId, frameId, instruction) {
  return api.post(`/generate/v1/projects/${projectId}/frames/${frameId}/regenerate`, {
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
  return api.post(`/generate/v1/projects/${projectId}/frames/${frameId}/regenerate-image`, {
    instruction,
  })
}
