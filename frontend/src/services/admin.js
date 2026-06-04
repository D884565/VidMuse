import api from './api'

// 数据概览
export const getDashboardStats = () => {
  return api.get('/v1/admin/dashboard/stats')
}

// 用户管理
export const getUserList = (params) => {
  return api.get('/v1/admin/users', { params })
}

export const createUser = (data) => {
  return api.post('/v1/admin/users', data)
}

export const updateUser = (id, data) => {
  return api.put(`/v1/admin/users/${id}`, data)
}

export const deleteUser = (id) => {
  return api.delete(`/v1/admin/users/${id}`)
}

// 内容管理
export const getContentList = (params) => {
  return api.get('/v1/admin/content', { params })
}

export const updateContentStatus = (id, status) => {
  return api.put(`/v1/admin/content/${id}/status`, { status })
}

export const deleteContent = (id) => {
  return api.delete(`/v1/admin/content/${id}`)
}

// 系统监控
export const getSystemStats = () => {
  return api.get('/v1/admin/system/stats')
}

export const getSystemLogs = (params) => {
  return api.get('/v1/admin/system/logs', { params })
}

// 模板管理
export const getTemplateList = (params) => {
  return api.get('/v1/admin/templates', { params })
}

export const createTemplate = (data) => {
  return api.post('/v1/admin/templates', data)
}

export const updateTemplate = (id, data) => {
  return api.put(`/v1/admin/templates/${id}`, data)
}

export const updateTemplateStatus = (id, status) => {
  return api.put(`/v1/admin/templates/${id}/status`, { status })
}

export const deleteTemplate = (id) => {
  return api.delete(`/v1/admin/templates/${id}`)
}
