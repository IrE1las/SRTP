import { computed, ref } from 'vue'
import { errorText } from './presentation.js'

export const isBooleanQuestion = question => ['bool', 'true_false'].includes(question?.kind)
export const blankCount = question => Math.max(1, Math.trunc(Number(question?.blank_count)) || 1)
export function initialAnswer(question) {
  if (question.kind === 'cell') return Array(blankCount(question)).fill('')
  return question.kind === 'multi' ? [] : null
}
export function hasAnswer(question, value) {
  if (isBooleanQuestion(question)) return typeof value === 'boolean'
  if (question.kind === 'multi') return Array.isArray(value) && value.length > 0
  if (question.kind === 'cell') return Array.isArray(value) && value.length === blankCount(question) && value.every(item => typeof item === 'string' && item.trim())
  return typeof value === 'string' && value.trim().length > 0
}
export function answerKeys(question, value) {
  if (Array.isArray(value)) return value
  if (question.kind === 'multi' && typeof value === 'string' && !question.options?.some(option => option.key === value)) return [...value]
  return value == null ? [] : [value]
}
export function answerText(question, value) {
  if (value == null) return '未提供'
  if (typeof value === 'boolean') return value ? '正确' : '错误'
  const display = item => {
    const option = question.options?.find(option => option.key === item)
    return option ? `${option.key}．${option.text}` : String(item)
  }
  if (question.kind === 'multi') return answerKeys(question, value).map(display).join('；')
  if (Array.isArray(value)) return value.map((item, index) => question.kind === 'cell' ? `第 ${index + 1} 空：${item}` : display(item)).join('；')
  return display(value)
}

const BASE = '/chapter-bank/practice'
// Drafts and server feedback belong to an attempt, never to the visible route.
export function createChapterPractice({ post, put, onBookmarkChange = () => {} }) {
  const sessions = ref({}), activeKey = ref(''), bookmarkPending = ref({})
  let epoch = 0, disposed = false
  const session = computed(() => sessions.value[activeKey.value])
  const history = computed(() => session.value?.history || [])
  const index = computed(() => session.value?.index ?? -1)
  const current = computed(() => history.value[index.value] || null)
  const busy = computed(() => Boolean(session.value?.loading || current.value?.submitting))
  const marking = computed(() => Boolean(bookmarkPending.value[current.value?.attempt.question.id]))
  const error = computed(() => session.value?.error || '')
  const empty = computed(() => session.value?.empty || '')

  async function draw() {
    const target = session.value, token = epoch
    if (!target || target.loading || disposed) return
    target.loading = true; target.error = ''; target.empty = ''
    try {
      const result = await post(`${BASE}/chapters/${encodeURIComponent(target.chapter)}/draw`, {
        exclude_ids: [...new Set(target.history.map(entry => entry.attempt.question.id))].slice(-1000), bookmarked_only: target.markedOnly,
      })
      if (token !== epoch || disposed) return
      if (!result?.question) { target.empty = target.markedOnly ? '本章暂无可练习的标记题目。' : '本章暂无可练习题目，未核验题目暂不出题。'; return }
      if (String(result.question.chapter) !== target.chapter) throw new Error('chapter mismatch')
      if (target.history.some(entry => entry.attempt.id === result.id)) {
        target.error = '抽到了重复题目，请重试下一题。'; return
      }
      target.history.push({ attempt: result, draft: result.submitted ? result.feedback?.submitted_answer : initialAnswer(result.question), submitting: false })
      target.index = target.history.length - 1
    } catch (failure) {
      if (token !== epoch || disposed) return
      if ([404, 409].includes(failure?.response?.status)) target.empty = errorText(failure, '本轮可练题目已练完。')
      else target.error = errorText(failure, '随机题目加载失败，请重试。')
    } finally { if (token === epoch && !disposed) target.loading = false }
  }
  async function setChapter(chapter, markedOnly = false) {
    if (session.value) session.value.loading = false
    epoch++
    const id = String(chapter || '')
    activeKey.value = id ? `${id}:${Boolean(markedOnly)}` : ''
    if (!id || disposed) return
    if (!sessions.value[activeKey.value]) sessions.value[activeKey.value] = { chapter: id, markedOnly: Boolean(markedOnly), history: [], index: -1, loading: false, error: '', empty: '' }
    if (!history.value.length) await draw()
  }
  async function next() {
    if (busy.value || !session.value || (current.value && !current.value.attempt.submitted)) return
    if (index.value < history.value.length - 1) { session.value.index++; session.value.error = ''; session.value.empty = ''; return }
    await draw()
  }
  function previous() { if (!busy.value && index.value > 0) { session.value.index--; session.value.error = ''; session.value.empty = '' } }
  async function submit() {
    const entry = current.value, target = session.value
    if (!entry || busy.value || entry.attempt.submitted || !hasAnswer(entry.attempt.question, entry.draft)) return
    entry.submitting = true; target.error = ''
    try {
      const result = await post(`${BASE}/attempts/${encodeURIComponent(entry.attempt.id)}/submit`, { answer: Array.isArray(entry.draft) ? [...entry.draft] : entry.draft })
      if (disposed) return
      if (result?.id !== entry.attempt.id || result?.question?.id !== entry.attempt.question.id) throw new Error('attempt mismatch')
      entry.attempt = { ...result, marked: entry.attempt.marked }
      entry.draft = result.feedback?.submitted_answer ?? entry.draft
    } catch (failure) { if (!disposed) target.error = errorText(failure, '提交失败，请重试；服务器保留首次提交结果。') }
    finally { entry.submitting = false }
  }
  async function toggleBookmark() {
    const entry = current.value, target = session.value
    if (!entry || marking.value || disposed) return
    const id = entry.attempt.question.id
    bookmarkPending.value[id] = true; target.error = ''
    try {
      const result = await put(`${BASE}/bookmarks/${encodeURIComponent(id)}`, { marked: !entry.attempt.marked })
      if (disposed) return
      for (const saved of Object.values(sessions.value)) for (const item of saved.history) if (item.attempt.question.id === id) item.attempt.marked = result.marked
      onBookmarkChange()
    } catch (failure) { if (!disposed) target.error = errorText(failure, '标记保存失败，请重试。') }
    finally { delete bookmarkPending.value[id] }
  }
  function restart() {
    if (!session.value || busy.value) return
    session.value.history = []; session.value.index = -1
    return draw()
  }
  function dispose() { disposed = true; epoch++; if (session.value) session.value.loading = false }
  return { current, history, index, busy, marking, error, empty, setChapter, next, previous, submit, toggleBookmark, restart, dispose }
}
