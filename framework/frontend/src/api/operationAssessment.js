import request from '@/utils/request'
export const getAssessmentConfig = id => request.get(`/operations/questions/${id}/assessment`)
export const saveAssessmentConfig = (id, body) => request.put(`/operations/questions/${id}/assessment`, body)
export const reviewAssessment = (id, body) => request.post(`/exams/attempts/${id}/assessment-review`, body)
export const generateStudentCommentary = (id, revision) => request.post(`/exams/attempts/${id}/student-commentary`, { revision }, { timeout:20000 })
export const getAssessmentEvidence = (id, after) => request.get(`/exams/attempts/${id}/evidence`, { params: { after, limit: 1 } })
