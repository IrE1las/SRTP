export function attemptStatus(status) {
  return ({ active: '进行中', submitted: '已提交', abandoned: '已放弃' })[status] || status
}
export function outcomeText(outcome) {
  return outcome?.status === 'correct' ? '100分' : outcome?.status === 'error' ? '错误' : 'null'
}
export function explanationStatus(status) {
  return ({ not_requested: '尚未生成', generating: '生成中', ready: '已生成', unconfigured: '未配置 AI',
    timeout: '请求超时', connection_error: '连接失败', invalid_response: '返回内容无效',
    service_error: '模型服务异常', context_too_large: '日志超出讲解容量' })[status] || status
}
export function learningError(error, fallback = '操作失败，请重试。') {
  return typeof error?.response?.data?.detail === 'string' ? error.response.data.detail : error?.message || fallback
}
export function learningDate(value) {
  if (!value) return 'null'
  const stamp = String(value)
  const date = new Date(/[zZ]|[+-]\d{2}:\d{2}$/.test(stamp) ? stamp : stamp + 'Z')
  if (Number.isNaN(date.getTime())) return 'null'
  return new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit',
    day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }).format(date)
}
