import request from '@/utils/request'
export const getLabQuestions = () => request.get('/lab-topics/questions')
export const getLabQuestion = key => request.get(`/lab-topics/questions/${key}`)
export const submitLabAnswer = (key, data) => request.post(`/lab-topics/questions/${key}/submit`, data)
export const getLabAttempts = () => request.get('/lab-topics/attempts')
export const getLabReviews = () => request.get('/lab-topics/reviews')
export const reviewLabAttempt = (id, data) => request.post(`/lab-topics/attempts/${id}/review`, data)
