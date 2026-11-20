export const objectiveKinds = { choice: '单选题', multi: '多选题', true_false: '判断题', cell: '填空题' }
export function emptyAnswer(question) {
  return question.kind === 'multi' ? [] : question.kind === 'cell' ? Array(question.blank_count).fill('') : null
}
export function answered(question, answer) {
  if (question.kind === 'cell') return Array.isArray(answer) && answer.length === question.blank_count && answer.every(value => typeof value === 'string' && value.trim())
  if (question.kind === 'multi') return Array.isArray(answer) && answer.length > 0
  return answer !== null && answer !== undefined && answer !== ''
}
export function answerText(answer) {
  if (answer === null || answer === undefined || answer === '' || Array.isArray(answer) && !answer.length) return '未作答'
  if (typeof answer === 'boolean') return answer ? '正确' : '错误'
  return Array.isArray(answer) ? answer.map(value => String(value).trim() || '未填写').join('、') : String(answer)
}
