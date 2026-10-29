export const completedMessage = '考试已完成，待教师确认并发布考试成绩'
export const examStates = { draft: '草稿', published: '已发布', open: '可参加', active: '进行中', upcoming: '未开始', missed: '已结束', submitted: '已交卷' }
export function examAction(exam) {
  return { open: '全屏参加考试', active: '恢复考试', upcoming: '未开始', missed: '已结束', submitted: '已结束' }[exam.state] || '不可参加'
}
export function examFormErrors(form, now = Date.now()) {
  const errors = {}
  if (!form.name.trim()) errors.name = '请填写考试名称'
  if (!form.classes.length) errors.classes = '请选择目标班级'
  if (!form.opens_at) errors.opens_at = '请选择开放时间'
  if (!form.closes_at) errors.closes_at = '请选择截止时间'
  const opens = Date.parse(form.opens_at + ':00+08:00'), closes = Date.parse(form.closes_at + ':00+08:00')
  if (form.opens_at && !Number.isFinite(opens)) errors.opens_at = '开放时间无效'
  if (form.closes_at && !Number.isFinite(closes)) errors.closes_at = '截止时间无效'
  if (Number.isFinite(opens) && Number.isFinite(closes) && opens >= closes) errors.closes_at = '截止时间必须晚于开放时间'
  else if (Number.isFinite(closes) && closes <= now) errors.closes_at = '截止时间必须晚于当前时间'
  if (!Number.isInteger(form.duration_minutes) || form.duration_minutes <= 0 || form.duration_minutes > 10080) errors.duration_minutes = '请填写1至10080的整数分钟'
  if (!form.version_id) errors.version_id = '请选择操作题版本'
  return errors
}
export function beijingTime(value) {
  return value ? new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }).format(new Date(value)) : 'null'
}
export function beijingInput(value) {
  if (!value) return ''
  return new Date(Date.parse(value) + 8 * 3600000).toISOString().slice(0, 16)
}
export function examPayload(form) {
  return { name: form.name.trim() || null, classes: [...form.classes], version_id: form.version_id || null,
    opens_at: form.opens_at ? form.opens_at + ':00+08:00' : null,
    closes_at: form.closes_at ? form.closes_at + ':00+08:00' : null,
    duration_minutes: form.duration_minutes || null }
}
export function secondsLeft(deadline, now) { return Math.max(0, Math.ceil((Date.parse(deadline) - now) / 1000)) }
export function clockText(seconds) { return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}` }
export function examError(error, fallback = '请求失败，请重试。') {
  const detail = error?.response?.data?.detail
  return typeof detail === 'string' ? detail : fallback
}
export async function enterExam(requestFullscreen, begin) {
  await requestFullscreen()
  return begin()
}

// Persist before any network request or navigation. IDs survive retries and
// acknowledgment only removes IDs actually accepted in that response.
export class ExamJournal {
  constructor(storage, key, clock = Date.now, uuid = () => crypto.randomUUID()) {
    this.storage = storage; this.key = key; this.clock = clock; this.uuid = uuid
    this.read()
  }
  read() {
    const raw = this.storage.getItem(this.key)
    const data = raw ? JSON.parse(raw) : { fullscreen: true, pending: [] }
    if (!Array.isArray(data.pending) || typeof data.fullscreen !== 'boolean') throw new Error('全屏恢复记录损坏，请保留本机数据并联系教师。')
    this.fullscreen = data.fullscreen; this.pending = data.pending
  }
  save() { this.storage.setItem(this.key, JSON.stringify({ fullscreen: this.fullscreen, pending: this.pending })) }
  observe(fullscreen) {
    this.read()
    if (fullscreen !== this.fullscreen) {
      this.pending.push({ event_id: this.uuid(), kind: fullscreen ? 'restore' : 'exit', occurred_at: new Date(this.clock()).toISOString() })
      this.fullscreen = fullscreen; this.save()
    }
  }
  acknowledge(ids) {
    this.read()
    const accepted = new Set(ids)
    this.pending = this.pending.filter(event => !accepted.has(event.event_id)); this.save()
  }
}
