import api from './api'

// 获取当前用户信息
export async function getUserInfo() {
  return api.get('/v1/users/me')
}

// 更新用户信息
export async function updateUserInfo(data) {
  return api.put('/v1/users/me', data)
}

// 修改密码
export async function changePassword(oldPassword, newPassword) {
  return api.put('/v1/users/me/password', {
    old_password: oldPassword,
    new_password: newPassword,
  })
}

// 退出登录
export async function logoutApi() {
  return api.post('/v1/auth/logout')
}
