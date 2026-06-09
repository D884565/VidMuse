import api from './api'

// 用户管理
export const getUserList = (params) => {
  return api.get('/v1/users', { params })
}

export const createUser = (data) => {
  return api.post('/v1/users', data)
}

export const updateUser = (id, data) => {
  return api.put(`/v1/users/${id}`, data)
}

export const deleteUser = (id) => {
  return api.delete(`/v1/users/${id}`)
}

// ==================== 商品分类管理 ====================
export const getCategoryTree = () => {
  return api.get('/v1/product/categories/tree')
}

export const getCategoriesByLevel = (level) => {
  return api.get(`/v1/product/categories/level/${level}`)
}

export const getCategoryInfo = (categoryId) => {
  return api.get(`/v1/product/categories/${categoryId}`)
}

export const createCategory = (data) => {
  return api.post('/v1/product/categories', data)
}

export const updateCategory = (categoryId, data) => {
  return api.put(`/v1/product/categories/${categoryId}`, data)
}

export const deleteCategory = (categoryId) => {
  return api.delete(`/v1/product/categories/${categoryId}`)
}

// ==================== 资产管理 ====================
export const getAssetList = (params) => {
  return api.get('/v1/assets', { params })
}

export const getAssetDetail = (assetId) => {
  return api.get(`/v1/assets/${assetId}`)
}

export const updateAsset = (assetId, data) => {
  return api.put(`/v1/assets/${assetId}`, data)
}

export const deleteAsset = (assetId) => {
  return api.delete(`/v1/assets/${assetId}`)
}

export const uploadInternalAsset = (formData) => {
  return api.post('/v1/assets/upload/internal', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

export const parseAsset = (assetId, force = false) => {
  return api.post(`/v1/assets/${assetId}/parse`, { force })
}

export const getParsingProgress = (assetId) => {
  return api.get(`/v1/assets/${assetId}/parsing-progress`)
}

export const retryParsing = (assetId) => {
  return api.post(`/v1/assets/${assetId}/retry-parsing`)
}

// ==================== 视频库管理 ====================
export const getVideoList = (params) => {
  return api.get('/v1/admin/video-library/', { params })
}

export const getVideoDetail = (videoId) => {
  return api.get(`/v1/admin/video-library/${videoId}`)
}

export const createVideo = (data) => {
  return api.post('/v1/admin/video-library', data)
}

export const uploadVideo = (formData) => {
  return api.post('/v1/admin/video-library/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

export const updateVideo = (videoId, data) => {
  return api.put(`/v1/admin/video-library/${videoId}`, data)
}

export const deleteVideo = (videoId) => {
  return api.delete(`/v1/admin/video-library/${videoId}`)
}

export const triggerVideoParsing = (videoId, force = false) => {
  return api.post(`/v1/admin/video-library/${videoId}/parse`, null, {
    params: { force }
  })
}

export const getVideoSlices = (videoId) => {
  return api.get(`/v1/admin/video-library/${videoId}/slices`)
}

export const batchImportHotVideos = (data) => {
  return api.post('/v1/admin/video-library/batch-import-hot', data)
}

// ==================== 灵感模板管理 ====================
// 创作因子接口
export const getFactorList = (params) => {
  return api.get('/v1/admin/inspiration/factors', { params })
}

export const getFactorDetail = (factorId) => {
  return api.get(`/v1/admin/inspiration/factors/${factorId}`)
}

export const createFactor = (data) => {
  return api.post('/v1/admin/inspiration/factors', data)
}

export const updateFactor = (factorId, data) => {
  return api.put(`/v1/admin/inspiration/factors/${factorId}`, data)
}

export const deleteFactor = (factorId) => {
  return api.delete(`/v1/admin/inspiration/factors/${factorId}`)
}

// 创作策略接口
export const getStrategyList = (params) => {
  return api.get('/v1/admin/inspiration/strategies', { params })
}

export const getStrategyDetail = (strategyId) => {
  return api.get(`/v1/admin/inspiration/strategies/${strategyId}`)
}

export const createStrategy = (data) => {
  return api.post('/v1/admin/inspiration/strategies', data)
}

export const updateStrategy = (strategyId, data) => {
  return api.put(`/v1/admin/inspiration/strategies/${strategyId}`, data)
}

export const deleteStrategy = (strategyId) => {
  return api.delete(`/v1/admin/inspiration/strategies/${strategyId}`)
}

// 灵感模板接口
export const getInspirationTemplateList = (params) => {
  return api.get('/v1/admin/inspiration/templates', { params })
}

export const getInspirationTemplateDetail = (templateId) => {
  return api.get(`/v1/admin/inspiration/templates/${templateId}`)
}

export const createInspirationTemplate = (data) => {
  return api.post('/v1/admin/inspiration/templates', data)
}

export const updateInspirationTemplate = (templateId, data) => {
  return api.put(`/v1/admin/inspiration/templates/${templateId}`, data)
}

export const deleteInspirationTemplate = (templateId) => {
  return api.delete(`/v1/admin/inspiration/templates/${templateId}`)
}

export const getTemplateFactors = (templateId) => {
  return api.get(`/v1/admin/inspiration/templates/${templateId}/factors`)
}

// 模板-因子关联接口
export const addTemplateFactorRelation = (data) => {
  return api.post('/v1/admin/inspiration/relations', data)
}

export const updateTemplateFactorRelation = (relationId, data) => {
  return api.put(`/v1/admin/inspiration/relations/${relationId}`, data)
}

export const deleteTemplateFactorRelation = (relationId) => {
  return api.delete(`/v1/admin/inspiration/relations/${relationId}`)
}

// ==================== 聚类分析接口 ====================
export const getClusterOverview = () => {
  return api.get('/v1/admin/inspiration/cluster/overview')
}

export const getClusterDetail = (clusterId) => {
  return api.get(`/v1/admin/inspiration/cluster/detail/${clusterId}`)
}

export const runClusterAnalysis = (params) => {
  return api.post('/v1/admin/inspiration/cluster/run', null, { params })
}

export const getClusterAnalysisStatus = (taskId) => {
  return api.get('/v1/admin/inspiration/cluster/status', { params: taskId ? { task_id: taskId } : {} })
}

// 获取关系图谱数据
export const getRelationGraph = (params) => {
  return api.get('/v1/admin/inspiration/relation-graph', { params })
}

// ==================== Agent追踪/监控（TraceManagement页面使用）====================
export const getTraceList = (params) => {
  return api.get('/v1/admin/agent/traces', { params })
}

export const getTraceDetail = (traceId) => {
  return api.get(`/v1/admin/agent/traces/${traceId}`)
}

export const getSessionTraces = (sessionId, params) => {
  return api.get(`/v1/admin/agent/traces/session/${sessionId}`, { params })
}

export const getUserTraces = (userId, params) => {
  return api.get(`/v1/admin/agent/traces/user/${userId}`, { params })
}

export const getTraceStatistics = (params) => {
  return api.get('/v1/admin/agent/traces/stats/overview', { params })
}

export const queryTraces = (data) => {
  return api.post('/v1/admin/agent/traces/query', data)
}

export const exportTraces = (params) => {
  return api.get('/v1/admin/agent/traces/export/data', { params })
}

// ==================== 系统请求链路追踪 ====================
export const getSystemTraceList = (params) => {
  return api.get('/v1/admin/traces', { params })
}

export const getSystemTraceDetail = (traceId) => {
  return api.get(`/v1/admin/traces/${traceId}`)
}

export const getSystemTraceSpans = (traceId, params = {}) => {
  return api.get(`/v1/admin/traces/${traceId}/spans`, { params })
}

export const getSystemSpanDetail = (spanId) => {
  return api.get(`/v1/admin/traces/spans/${spanId}`)
}

export const getSystemTraceStatistics = (params) => {
  return api.get('/v1/admin/traces/stats/overview', { params })
}

export const querySystemTraces = (data) => {
  return api.post('/v1/admin/traces/query', data)
}

// ==================== 流水线管理 ====================
export const getPipelineList = (params) => {
  return api.get('/v1/admin/pipelines/', { params })
}

export const getPipelineStatistics = () => {
  return api.get('/v1/admin/pipelines/statistics')
}

export const getPipelineDetail = (executionId) => {
  return api.get(`/v1/admin/pipelines/${executionId}`)
}

export const retryPipeline = (executionId, data = {}) => {
  return api.post(`/v1/admin/pipelines/${executionId}/retry`, data)
}

export const cancelPipeline = (executionId) => {
  return api.post(`/v1/admin/pipelines/${executionId}/cancel`)
}


