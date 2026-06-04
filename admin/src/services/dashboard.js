import request from '@/utils/request'

export function getStats() {
  return request({
    url: '/admin/dashboard/stats',
    method: 'get',
  })
}

export function getSystemMetrics() {
  return request({
    url: '/admin/dashboard/system-metrics',
    method: 'get',
  })
}

export function getRecentErrors() {
  return request({
    url: '/admin/dashboard/recent-errors',
    method: 'get',
  })
}
