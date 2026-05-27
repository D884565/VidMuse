import api from './api'

// 用户登录
export async function login(username, password) {
  return api.post('/generate/v1/auth/login', { username, password })
}

// 用户注册
export async function register(username, password, avatarUrl) {
  return api.post('/generate/v1/auth/register', {
    username,
    password,
    avatar_url: avatarUrl,
  })
}
