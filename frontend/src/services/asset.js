import api from './api'

/**
 * 获取素材列表
 * @param {Object} params - 查询参数
 * @param {number} [params.type] - 资产类型筛选 (1=图片, 2=视频, 3=音频)
 * @param {number} [params.page] - 页码
 * @param {number} [params.page_size] - 每页数量
 */
export async function listAssets(params = {}) {
  return api.get('/rag/v1/assets', { params })
}

/**
 * 上传素材
 * @param {FormData} formData - 必须包含 file 和 type 字段
 */
export async function uploadAsset(formData) {
  return api.post('/rag/v1/assets/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

// 删除素材
export async function deleteAsset(assetId) {
  return api.delete(`/rag/v1/assets/${assetId}`)
}
