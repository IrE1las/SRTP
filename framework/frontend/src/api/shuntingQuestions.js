import request from '@/utils/request'

export function listShuntingQuestions() {
  return request.get('/exam/shunting/questions')
}

export function getShuntingQuestion(id) {
  return request.get(`/exam/shunting/questions/${id}`)
}

export function submitShuntingQuestion(id, answer) {
  return request.post(`/exam/shunting/questions/${id}/submit`, answer)
}
