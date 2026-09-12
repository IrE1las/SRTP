import request from '@/utils/request'

export function listTeacherExercises() {
  return request.get('/exercises/teacher')
}

export function createExercise(data) {
  return request.post('/exercises', data)
}

export function updateExercise(exerciseId, data) {
  return request.put(`/exercises/${exerciseId}`, data)
}

export function deleteExercise(exerciseId) {
  return request.delete(`/exercises/${exerciseId}`)
}

export function listLobbyExercises() {
  return request.get('/exercises/lobby')
}

export function getExercise(exerciseId) {
  return request.get(`/exercises/${exerciseId}`)
}

export function startExercise(exerciseId) {
  return request.post('/exercise-sessions/start', { exercise_id: Number(exerciseId) })
}

export function finishExercise(sessionId, reason = 'aborted') {
  return request.post(`/exercise-sessions/${sessionId}/finish`, { reason })
}

export function getExerciseHistory() {
  return request.get('/exercise-sessions/history')
}

export function getExerciseReplay(sessionId) {
  return request.get(`/exercise-sessions/${sessionId}/replay`)
}
