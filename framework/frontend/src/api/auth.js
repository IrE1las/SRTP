import request from '@/utils/request'

export function login(data) { return request.post('/auth/login', data) }
export function getCurrentUser() { return request.get('/auth/me') }
export function updateContact(data) { return request.put('/auth/me/contact', data) }
export function changePassword(data) { return request.post('/auth/me/password', data) }
