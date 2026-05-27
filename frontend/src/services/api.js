import axios from 'axios'
import { useAppStore } from '../store/appStore'

// 创建 axios 实例，baseURL 为 /api，由 Vite 代理转发到后端
const api = axios.create({
  baseURL: '/api',
})

// 请求拦截器：自动注入 Authorization token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// 响应拦截器：解包响应信封，处理错误
api.interceptors.response.use(
  (response) => {
    const { code, message, data } = response.data
    // 业务状态码非 "0000000" 视为失败
    if (code !== '0000000') {
      return Promise.reject(new Error(message || '请求失败'))
    }
    // 返回解包后的 data
    return data
  },
  (error) => {
    // 401 未授权：清除 token 并跳转登录页
    if (error.response && error.response.status === 401) {
      localStorage.removeItem('token')
      useAppStore.getState().setIsLoggedIn(false)
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default api
