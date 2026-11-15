import request from '@/utils/request'
const root = '/operations'
export const getOperationClasses = () => request.get(root + '/classes')
export const deleteOperation = (id, force = false) => request.delete(`${root}/questions/${id}`, { params: { force } })
export const getOperationDeletion = id => request.get(`${root}/questions/${id}/deletion`)
export const getOperationStation = () => request.get(root + '/station')
export const listOperations = (page = 1, filters = {}) => request.get(root + '/questions', { params: { page, ...filters } })
export const getOperation = id => request.get(`${root}/questions/${id}`)
export const getOperationVersion = (id, number) => request.get(`${root}/questions/${id}/versions/${number}`)
export const createOperation = data => request.post(root + '/questions', data)
export const updateOperation = (id, data) => request.put(`${root}/questions/${id}`, data)
export const publishOperation = id => request.post(`${root}/questions/${id}/publish`)
export const disableOperation = id => request.post(`${root}/questions/${id}/disable`)
export const startOperationSession = (id, kind) => request.post(`${root}/questions/${id}/sessions`, { kind })
export const getOperationSession = id => request.get(`${root}/sessions/${id}`)
export const postOperationEvent = (id, event) => request.post(`${root}/sessions/${id}/events`, event)
export const stopOperationSession = id => request.post(`${root}/sessions/${id}/stop`)
export const saveOperationStandard = id => request.post(`${root}/sessions/${id}/save-standard`)
export async function downloadOperationLog(id) {
  const content = await request.get(`${root}/sessions/${id}/log.json`)
  const url = URL.createObjectURL(new Blob([JSON.stringify(content, null, 2)], { type: 'application/json;charset=utf-8' }))
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `operation-${id}.json`
  anchor.click()
  URL.revokeObjectURL(url)
}
