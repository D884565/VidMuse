import api from './api'

// 创建新项目
export async function createProject(data) {
  return api.post('/generate/v1/projects', data)
}

// 获取项目详情（轮询用）
export async function getProjectDetail(projectId) {
  return api.get(`/generate/v1/projects/${projectId}`)
}

/**
 * 获取项目列表
 * @param {Object} params - 查询参数
 * @param {number} [params.status] - 状态筛选 (0=待生成, 1=生成中, 2=已完成, 3=失败)
 * @param {string} [params.keyword] - 关键词搜索
 * @param {string} [params.start_date] - 开始日期 YYYY-MM-DD
 * @param {string} [params.end_date] - 结束日期 YYYY-MM-DD
 * @param {number} [params.page] - 页码
 * @param {number} [params.page_size] - 每页数量
 */
export async function getProjects(params = {}) {
  return api.get('/rag/v1/projects', { params })
}
