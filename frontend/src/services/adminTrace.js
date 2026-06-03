import api from './api'

/**
 * 分页查询轨迹列表
 * @param {Object} params 查询参数
 * @param {string} [params.session_id] 会话ID
 * @param {number} [params.user_id] 用户ID
 * @param {number} [params.project_id] 项目ID
 * @param {string} [params.model] 模型名称
 * @param {boolean} [params.success] 执行结果
 * @param {string} [params.start_time] 开始时间 ISO格式
 * @param {string} [params.end_time] 结束时间 ISO格式
 * @param {string} [params.keyword] 关键词搜索
 * @param {number} [params.page] 页码
 * @param {number} [params.page_size] 每页数量
 */
export const getTraceList = (params) => api.get('/agent/traces', { params })

/**
 * 获取轨迹详情
 * @param {number} traceId 轨迹ID
 */
export const getTraceDetail = (traceId) => api.get(`/agent/traces/${traceId}`)

/**
 * 获取统计概览数据
 * @param {Object} params 查询参数
 * @param {string} [params.period] 统计周期：1d/7d/30d/all
 * @param {number} [params.user_id] 用户ID筛选
 * @param {number} [params.project_id] 项目ID筛选
 */
export const getTraceStats = (params) => api.get('/agent/traces/stats/overview', { params })

/**
 * 查询会话的所有轨迹
 * @param {string} sessionId 会话ID
 * @param {number} [page] 页码
 * @param {number} [page_size] 每页数量
 */
export const getSessionTraces = (sessionId, page = 1, page_size = 20) =>
  api.get(`/agent/traces/session/${sessionId}`, { params: { page, page_size } })

/**
 * 查询用户的所有轨迹
 * @param {number} userId 用户ID
 * @param {number} [page] 页码
 * @param {number} [page_size] 每页数量
 */
export const getUserTraces = (userId, page = 1, page_size = 20) =>
  api.get(`/agent/traces/user/${userId}`, { params: { page, page_size } })

/**
 * 导出轨迹数据
 * @param {Object} params 导出筛选参数
 */
export const exportTraces = (params) => api.get('/agent/traces/export/data', { params })
