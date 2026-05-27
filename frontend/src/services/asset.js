import api from './api'

// 获取素材列表
export async function listAssets() {
  return api.get('/rag/v1/assets')
}

// 上传素材
export async function uploadAsset(formData) {
  return api.post('/rag/v1/assets', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

// 删除素材
export async function deleteAsset(assetId) {
  return api.delete(`/rag/v1/assets/${assetId}`)
}
