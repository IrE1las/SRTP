export const QUESTION_KINDS = [
  { value: 'objective', label: '客观全部' },
  { value: 'choice', label: '单选题' },
  { value: 'multi', label: '多选题' },
  { value: 'cell', label: '填空题' },
  { value: 'true_false', label: '判断题' },
  { value: 'essay', label: '主观备选' },
]

export function kindLabel(value) {
  return QUESTION_KINDS.find(kind => kind.value === value)?.label || '其他题型'
}

export function isAnswered(value) {
  return ['exam_answer_key', 'local_rule_checked', 'material_supported', 'source_explicit'].includes(value)
}

export function answerStatusLabel(value) {
  return { partial: '部分待核验', platform_answer: '待独立核验' }[value]
    || (isAnswered(value) ? '已有答案依据' : '待核验')
}

export function referenceNotice(value) {
  if (isAnswered(value)) return ''
  return {
    partial: '部分内容待核验，下列资料仅供核对，不能作为完整标准答案。',
    platform_answer: '平台参考答案待独立核验，请结合本地规则与原始资料复核。',
  }[value] || '参考答案待核验；未提供的内容不代表题目没有答案。'
}

export function scopeLabel(value) {
  return { general: '通用知识', station_specific: '依赖指定站场', station: '依赖指定站场' }[value] || value
}

export function sourceKindLabel(value) {
  return {
    scanned_original: '扫描资料原题', local_scan: '扫描资料题', local_original: '本地资料题', courseware_adapted: '课件改编',
    web_original: '公开资料原题', web_adapted: '公开资料改编', web_supplement: '公开资料补充', ppt_original_prompt: '课件原题',
  }[value] || '资料题'
}

export function safeSourceUrl(value) {
  if (typeof value !== 'string') return ''
  try {
    const url = new URL(value)
    return ['http:', 'https:'].includes(url.protocol) ? value : ''
  } catch { return '' }
}

export function formatReferenceValue(value) {
  if (value == null) return '未提供'
  if (typeof value === 'boolean') return value ? '正确（是）' : '错误（否）'
  if (typeof value === 'string') return value.trim() || '未提供'
  if (Array.isArray(value)) return value.length ? value.map(formatReferenceValue).join('；') : '未提供'
  if (typeof value === 'object') {
    const entries = Object.entries(value)
    return entries.length ? entries.map(([key, item]) => `${key}：${formatReferenceValue(item)}`).join('\n') : '未提供'
  }
  return String(value)
}

export function objectiveStats(chapter = {}) {
  const count = value => value != null && value !== '' && Number.isFinite(Number(value)) ? Number(value) : null
  return {
    total: count(chapter.objective) ?? 0,
    ready: count(chapter.objective_ready),
    pending: count(chapter.objective_pending),
  }
}

export function errorText(error, fallback) {
  const detail = error?.response?.data?.detail
  return typeof detail === 'string' ? detail : fallback
}
