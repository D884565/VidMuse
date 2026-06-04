import request from '@/utils/request'

export function login(data) {
  return request({
    url: '/admin/auth/login',
    method: 'post',
    data,
  })
}

export function logout() {
  return request({
    url: '/admin/auth/logout',
    method: 'post',
  })
}

export function getProfile() {
  return request({
    url: '/admin/auth/profile',
    method: 'get',
  })
}
