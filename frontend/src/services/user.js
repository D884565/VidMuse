import api from './api'

export async function getUserInfo(config = {}) {
  return api.get('/v1/users/me', config)
}

export async function updateUserInfo(data) {
  return api.put('/v1/users/me', data)
}

export async function changePassword(oldPassword, newPassword) {
  return api.put('/v1/users/me/password', {
    old_password: oldPassword,
    new_password: newPassword,
  })
}

export async function logoutApi() {
  return api.post('/v1/auth/logout')
}
