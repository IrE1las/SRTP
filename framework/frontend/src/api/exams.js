import request from '@/utils/request'
const root = '/exams'
export const listExams = (page = 1) => request.get(root, { params: { page } })
export const getExam = id => request.get(`${root}/${id}`)
export const createExam = body => request.post(root, body)
export const editExam = (id, body) => request.put(`${root}/${id}`, body)
export const publishExam = (id, revision) => request.post(`${root}/${id}/publish`, { revision })
export const withdrawExam = (id, revision) => request.post(`${root}/${id}/withdraw`, { revision })
export const copyExam = id => request.post(`${root}/${id}/copy`)
export const examVersions = (page = 1, search = '') => request.get(root + '/versions', { params: { page, search } })
export const examParticipants = (id, page = 1) => request.get(`${root}/${id}/participants`, { params: { page } })
export const examAttempts = (id, page = 1) => request.get(`${root}/${id}/attempts`, { params: { page } })
export const examHistory = (page = 1) => request.get(root + '/history', { params: { page } })
export const beginExam = id => request.post(`${root}/${id}/begin`, { fullscreen: true })
export const getExamAttempt = id => request.get(`${root}/attempts/${id}`)
export const syncExam = (id, body) => request.post(`${root}/attempts/${id}/sync`, body, { quiet: true })
export const submitExam = (id, sequence) => request.post(`${root}/attempts/${id}/submit`, { expected_sequence: sequence })
export const examStation = () => request.get(root + '/station')
export const examEvent = (id, event) => request.post(`${root}/attempts/${id}/events`, event)
export const saveExamGrade = (id, body) => request.put(`${root}/attempts/${id}/grade`, body)
export const confirmExamGrade = (id, revision) => request.post(`${root}/attempts/${id}/grade/confirm`, { revision })
export const publishExamGrade = (id, revision) => request.post(`${root}/attempts/${id}/grade/publish`, { revision })
// Best-effort delivery when a live page closes. Retain the local queue until a
// normal acknowledged sync; a lost keepalive response must not erase evidence.
export function reportExamExit(id, events) {
  const token = localStorage.getItem('railway_access_token')
  const base = (request.defaults.baseURL || '/api').replace(/\/$/, '')
  return fetch(`${base}${root}/attempts/${encodeURIComponent(id)}/sync`, {
    method: 'POST', keepalive: true,
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token || ''}` },
    body: JSON.stringify({ fullscreen: false, events }),
  })
}
export async function downloadExam(id) {
  const content = await request.get(`${root}/attempts/${id}/log.json`)
  const url = URL.createObjectURL(new Blob([JSON.stringify(content, null, 2)], { type: 'application/json;charset=utf-8' }))
  const anchor = document.createElement('a'); anchor.href = url; anchor.download = `exam-${id}.json`; anchor.click(); URL.revokeObjectURL(url)
}
