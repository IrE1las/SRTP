import request from '@/utils/request'
export const getLabQuestions = () => request.get('/lab-topics/questions')
export const getLabQuestion = key => request.get(`/lab-topics/questions/${key}`)
export const submitLabAnswer = (key, data) => request.post(`/lab-topics/questions/${key}/submit`, data)
export const getLabAttempts = topic => request.get('/lab-topics/attempts', { params: { topic } })
export const getLabReviews = topic => request.get('/lab-topics/reviews', { params: { topic } })
export const reviewLabAttempt = (id, data) => request.post(`/lab-topics/attempts/${id}/review`, data)

export const getReviewStudents = topic => request.get('/lab-topics/review-students', { params: { topic } })
export const getReviewStudentAttempts = (id,topic) => request.get('/lab-topics/review-students/' + encodeURIComponent(id) + '/attempts', { params: { topic } })
export const getReviewAttempt = id => request.get('/lab-topics/review-attempts/' + encodeURIComponent(id))

export const getLabAttemptPage = (topic,page=1) => request.get('/lab-topics/attempts/page', { params: { topic,page,page_size:6 } })
export const getLabAttempt = id => request.get('/lab-topics/attempts/' + encodeURIComponent(id))
