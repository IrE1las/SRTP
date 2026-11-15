import request from '@/utils/request'

export function getAdminOverview() {
  return request.get('/admin/overview')
}

export function listAdminUsers() {
  return request.get('/admin/users')
}

export function updateAdminUser(userId, data) {
  return request.put(`/admin/users/${userId}`, data)
}

export function deleteAdminUser(userId) {
  return request.delete(`/admin/users/${userId}`)
}
