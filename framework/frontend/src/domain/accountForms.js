// Validation details contain field locations and messages, never request values.
export function accountError(error) {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map(item => item.msg).join('；')
  return '请求失败，请重试'
}
