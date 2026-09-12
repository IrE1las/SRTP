import request from '@/utils/request'

export function generateAiScore(sessionId) {
  return request.post(`/ai-scores/sessions/${sessionId}/generate`)
}

export function getAiScore(sessionId) {
  return request.get(`/ai-scores/sessions/${sessionId}`)
}

export function listMyAiScores() {
  return request.get('/ai-scores/me')
}
