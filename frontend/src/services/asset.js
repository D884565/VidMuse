import api from './api'

export async function listAssets(params = {}) {
  return api.get('/v1/assets', { params })
}

export async function uploadAsset(formData) {
  return api.post('/v1/assets/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export async function createTextAsset(payload) {
  return api.post('/v1/assets/text', payload)
}

export async function updateTextAsset(assetId, payload) {
  return api.put(`/v1/assets/${assetId}/text`, payload)
}

export async function initResumableUpload(payload) {
  return api.post('/v1/assets/upload/init', payload)
}

export async function uploadImageChunk(formData) {
  return api.put('/v1/assets/upload/chunk', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export async function getUploadStatus(sessionId) {
  return api.get('/v1/assets/upload/status', { params: { session_id: sessionId } })
}

export async function completeResumableUpload(payload) {
  return api.post('/v1/assets/upload/complete', payload)
}

export async function initImageReupload(assetId, payload) {
  return api.post(`/v1/assets/${assetId}/reupload/init`, payload)
}

export async function completeImageReupload(assetId, payload) {
  return api.post(`/v1/assets/${assetId}/reupload/complete`, payload)
}

export async function reuploadImageAsset(assetId, formData) {
  return api.post(`/v1/assets/${assetId}/reupload`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export async function updateAsset(assetId, data) {
  return api.put(`/v1/assets/${assetId}`, data)
}

export async function deleteAsset(assetId) {
  return api.delete(`/v1/assets/${assetId}`)
}
