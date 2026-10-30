export const gradeStates = { ungraded: '待批阅', draft: '成绩草稿', confirmed: '已确认，未发布', published: '已发布' }
export const gradeActions = { save: '保存草稿', confirm: '确认成绩', publish: '发布成绩' }
export function gradeError(score) {
  if (String(score).trim() === '') return ''
  const value = String(score).trim()
  return /^\d+(\.\d{1,2})?$/.test(value) && Number(value) <= 100 ? '' : '请输入0—100的成绩，最多两位小数。'
}
export function gradePayload(form, revision) {
  return { revision, score: String(form.score).trim() || null, comment: form.comment.trim() || null }
}
