import request from '@/utils/request'
const root = '/chapter-bank/manage/questions'
export const listChapterQuestions = params => request.get(root, { params })
export const getChapterQuestion = id => request.get(`${root}/${encodeURIComponent(id)}`)
export const createChapterQuestion = body => request.post(root, body)
export const editChapterQuestion = (id, body) => request.put(`${root}/${encodeURIComponent(id)}`, body)
export const deleteChapterQuestion = (id, revision) => request.delete(`${root}/${encodeURIComponent(id)}`, { params: { revision } })
