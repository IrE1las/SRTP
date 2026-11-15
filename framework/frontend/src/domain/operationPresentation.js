import { COMMANDS } from '../features/simulationConsole/standardDisplay.js'

export const operationBase = '/operations/manage'
export const operationPath = (id, step = 'edit') => `${operationBase}/${id}/${step}`
export const operationReturn = value => typeof value === 'string' && value.length <= 2000 && /^\/operations\/manage(?:\?|$)/.test(value) ? value : operationBase
export function operationLocation(id, step = 'edit', back = operationBase, query = {}) {
  const returnTo = operationReturn(back)
  return { path: operationPath(id, step), query: { ...(returnTo === operationBase ? {} : { back: returnTo }), ...query } }
}
export const operationStatus = value => ({ draft: '草稿', published: '已发布', disabled: '已停用' })[value] || value
export const sessionStatus = value => ({ active: '进行中', stopped: '已结束', abandoned: '已封存' })[value] || value
export const actionLabel = value => ({ function: '选择功能', target: '选择设备', button: '进路按钮', cancel_selection: '取消选择' })[value] || value
export const buttonLabel = value => COMMANDS.find(item => item.type === value)?.label || ({ BLOCK_REQUEST: '请求发车', BLOCK_RESET: '复原', BLOCK_ACCIDENT_RESET: '事故复原', BLOCK_TOTAL_AUX: '总辅助', BLOCK_DEPARTURE_AUX: '发车辅助', BLOCK_RECEPTION_AUX: '接车辅助' })[value] || value || '—'
export function operationError(error, fallback = '操作失败，请重试。') {
  const detail = error?.response?.data?.detail
  return typeof detail === 'string' ? detail : error?.message || fallback
}
export function draftErrors(data) {
  const errors = {}
  if (!data.title?.trim()) errors.title = '请输入题目标题。'
  if (!data.prompt?.trim()) errors.prompt = '请输入学生需要完成的任务。'
  if (!data.classes.length) errors.classes = '请至少添加一个目标班级。'
  else if (data.classes.some(name => name.length > 100)) errors.classes = '每个班级名称不能超过 100 字。'
  if (data.classes.length > 100) errors.classes = '最多添加 100 个班级。'
  return errors
}
export function canSaveRecording(question, session, sessions, sid) {
  return question?.status === 'draft' && !question.disabled && session?.status === 'stopped' &&
    session.snapshot?.session_kind === 'recording' &&
    sessions.some(item => item.id === sid && item.version_id === question.version_id)
}
export function publishIssues(question, sessions = []) {
  if (!question) return []
  const issues = Object.values(draftErrors(question))
  if (!question.standard_session_id || !question.standard_log?.length) issues.push('录制并保存一份标准答案。')
  else if (!question.standard_log.some(event => ['button', 'target'].includes(event.action) && event.result?.accepted)) issues.push('标准答案需要包含有效的设备或进路操作。')
  if (sessions.some(item => item.version_id === question.version_id && item.status === 'active')) issues.push('先结束该版本仍在进行的录制或预览。')
  return issues
}
