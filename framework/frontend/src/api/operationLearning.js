import request from '@/utils/request'
const root = '/operation-learning'
export const beginLearning = (id, restartFrom = null) => request.post(`${root}/questions/${id}/begin`, { restart_from: restartFrom })
export const getLearning = id => request.get(`${root}/attempts/${id}`)
export const listLearning = (page = 1, filters = {}) => request.get(root + '/attempts', { params: { page, ...filters } })
export const submitLearning = id => request.post(`${root}/attempts/${id}/submit`, {})
export const explainLearning = id => request.post(`${root}/attempts/${id}/explanation`, {}, { timeout: 20000 })
export const reviewLearning = (id, body) => request.put(`${root}/attempts/${id}/review`, body)
export const learningConsoleApi = {
  station: () => request.get(root + '/station'),
  console: id => request.get(`${root}/attempts/${id}/console`),
  event: (id, event) => request.post(`${root}/attempts/${id}/events`, event),
}
export async function downloadLearning(id) {
  const content = await request.get(`${root}/attempts/${id}/log.json`)
  const url = URL.createObjectURL(new Blob([JSON.stringify(content, null, 2)], { type: 'application/json;charset=utf-8' }))
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `learning-${id}.json`
  anchor.click()
  URL.revokeObjectURL(url)
}
