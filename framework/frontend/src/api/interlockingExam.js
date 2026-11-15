import request from '@/utils/request'

/** Step 1: 快速本地比对，不调用 AI */
export function submitInterlockingExam(data) {
  return request.post('/exam/submit', data)
}

/** Step 2: 学生点击「AI 解析」后调用，可能较慢 */
export function requestAiExplanation(data, signal) {
  return request.post('/exam/ai-explain', data, { timeout: 120000, signal })
}
