import { post } from '@/utils/request'

// 登录
export const login = (data) => {
  return post('/admin/login', data)
}

// 登出
export const logout = () => {
  return post('/admin/logout')
}
