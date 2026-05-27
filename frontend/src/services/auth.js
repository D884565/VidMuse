import api from './api'

// 用户登录 - 返回完整响应（access_token, refresh_token, user_id, username, role, expires_in）
export async function login(username, password) {
  return api.post('/generate/v1/auth/login', { username, password })
}

// 用户注册 - 返回完整响应
export async function register(username, password, avatarUrl) {
  return api.post('/generate/v1/auth/register', {
    username,
    password,
    avatar_url: avatarUrl,
  })
}

// 刷新 token
export async function refreshToken(refreshTokenValue) {
  return api.post(`/generate/v1/auth/refresh?refresh_token=${encodeURIComponent(refreshTokenValue)}`)
}
