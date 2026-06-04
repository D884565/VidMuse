import { get, download } from '@/utils/request'

// 获取统计概览
export const getTraceStats = (params) => {
  return get('/agent/traces/stats/overview', params)
}

// 获取轨迹列表
export const getTraceList = (params) => {
  return get('/agent/traces', params)
}

// 获取轨迹详情
export const getTraceDetail = (id) => {
  return get(`/agent/traces/${id}`)
}

// 获取会话轨迹
export const getSessionTraces = (sessionId, params) => {
  return get(`/agent/traces/session/${sessionId}`, params)
}

// 导出轨迹数据
export const exportTraces = (params) => {
  return download('/agent/traces/export/data', params)
}
