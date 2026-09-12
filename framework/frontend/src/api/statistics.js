import request from '@/utils/request'

export function getMyStatistics() {
  return request.get('/statistics/student/me')
}

export function getTeacherStatistics() {
  return request.get('/statistics/teacher/overview')
}
