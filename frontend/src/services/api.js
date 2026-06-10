import axios from 'axios'
import { useAppStore } from '../store/appStore'

// 创建 axios 实例，baseURL 为 /api，由 Vite 代理转发到后端
const api = axios.create({
  baseURL: '/api',
  timeout: 120000,
})

// 请求拦截器：自动注入 Authorization token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      // 先删除可能存在的小写authorization头，避免冲突
      delete config.headers.authorization
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// refresh 锁：防止多个 401 请求同时触发多次 refresh
let refreshPromise = null

async function doRefresh() {
  const refreshTokenValue = localStorage.getItem('refresh_token')
  if (!refreshTokenValue) throw new Error('无 refresh_token')

  // 直接用 axios 调用，避免走拦截器导致循环
  // refresh_token 放请求体，避免进入服务器访问日志和浏览器历史。
  const resp = await axios.post(
    '/api/v1/auth/refresh',
    { refresh_token: refreshTokenValue },
    { timeout: 30000 }
  )
  const { code, data } = resp.data
  if (code !== '0000000' || !data?.access_token) {
    throw new Error('refresh 失败')
  }
  localStorage.setItem('token', data.access_token)
  return data.access_token
}

// 响应拦截器：解包响应信封，处理 401 自动刷新
api.interceptors.response.use(
  (response) => {
    if (response.config?.responseType === 'blob') {
      return response
    }
    const { code, message, data } = response.data
    // 业务状态码非 "0000000" 视为失败
    if (code !== '0000000') {
      return Promise.reject(new Error(message || '请求失败'))
    }
    // 返回解包后的 data
    return data
  },
  async (error) => {
    const originalRequest = error.config

    // 401 且未重试过：尝试刷新 token
    if (error.response?.status === 401 && !originalRequest._retried) {
      originalRequest._retried = true

      try {
        // 使用 refresh 锁，多个请求共享同一个 refresh 操作
        if (!refreshPromise) {
          refreshPromise = doRefresh()
        }
        await refreshPromise
        refreshPromise = null

        // 手动设置新的token，确保使用最新的，避免依赖拦截器可能的问题
        const newToken = localStorage.getItem('token')
        originalRequest.headers.Authorization = `Bearer ${newToken}`
        // 清除可能存在的小写authorization头，避免冲突
        delete originalRequest.headers.authorization
        // 重放请求
        return api(originalRequest)
      } catch (refreshErr) {
        refreshPromise = null
        // refresh 也失败，统一走登出流程，避免遗漏 authLoading 等状态。
        useAppStore.getState().logout()
        window.location.href = '/login'
        return Promise.reject(refreshErr)
      }
    }

    return Promise.reject(error)
  }
)

export default api
