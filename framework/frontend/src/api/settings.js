import request from '@/utils/request'

export function getAiSettings() {
  return request.get('/settings/ai')
}

export function updateAiSettings(data) {
  return request.put('/settings/ai', data)
}

export function testAiConnection(data) {
  return request.post('/settings/ai/test', data)
}
