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

export function createAdminUser(data) {
  return request.post('/admin/users', data)
}

export function resetAdminPassword(userId, data) {
  return request.post(`/admin/users/${userId}/reset-password`, data)
}

export function unlockAdminContact(userId) {
  return request.post(`/admin/users/${userId}/unlock-contact`)
}
