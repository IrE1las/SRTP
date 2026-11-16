import { computed, ref } from 'vue'
import { errorText } from './presentation.js'
import { hasAnswer, initialAnswer } from './useChapterPractice.js'

const BASE = '/chapter-bank/practice'
export const studyState = (entry) =>
  entry.ever_correct ? '曾做对' : entry.attempted ? '尚未做对' : '未作答'
export const hasDraft = (value) =>
  typeof value === 'boolean' ||
  (Array.isArray(value)
    ? value.some((item) => typeof item === 'string' && item.trim())
    : typeof value === 'string' && Boolean(value.trim()))
export function createChapterStudy({
  get,
  post,
  put,
  onProgressChange = () => {},
}) {
  const sessions = ref({}),
    active = ref('')
  let disposed = false
  const session = computed(() => sessions.value[active.value])
  const entries = computed(() => session.value?.entries || [])
  const loading = computed(() => Boolean(session.value?.loading))
  const error = computed(() => session.value?.error || '')
  const filters = ref({ kind: '', progress: '', search: '' })
  const selected = ref('')
  // Keep a just-submitted question in place so its feedback can be read.
  const visibleIds = ref([])
  const filtered = computed(() =>
    entries.value.filter((entry) =>
      visibleIds.value.includes(entry.question.id),
    ),
  )
  const current = computed(
    () =>
      filtered.value.find((entry) => entry.question.id === selected.value) ||
      filtered.value[0],
  )
  const stats = computed(() => ({
    total: entries.value.length,
    attempted: entries.value.filter((e) => e.attempted).length,
    correct: entries.value.filter((e) => e.ever_correct).length,
    marked: entries.value.filter((e) => e.marked).length,
  }))

  function applyFilters(patch = {}) {
    filters.value = { ...filters.value, ...patch }
    const { kind, progress, search } = filters.value
    const term = search.trim().toLocaleLowerCase()
    visibleIds.value = entries.value
      .filter(
        (entry) =>
          (!kind || entry.question.kind === kind) &&
          (!term ||
            `${entry.question.stem} ${entry.question.id}`
              .toLocaleLowerCase()
              .includes(term)) &&
          (!progress ||
            (progress === 'marked' && entry.marked) ||
            (progress === 'unanswered' && !entry.attempted) ||
            (progress === 'not_correct' && !entry.ever_correct) ||
            (progress === 'correct' && entry.ever_correct)),
      )
      .map((entry) => entry.question.id)
    if (!visibleIds.value.includes(selected.value))
      selected.value = visibleIds.value[0] || ''
  }
  async function setChapter(id, markedOnly = false) {
    active.value = String(id || '')
    filters.value = {
      kind: '',
      progress: markedOnly ? 'marked' : '',
      search: '',
    }
    selected.value = ''
    visibleIds.value = []
    if (!id || disposed) return
    if (!sessions.value[id])
      sessions.value[id] = {
        entries: [],
        loaded: false,
        loading: false,
        error: '',
      }
    const target = sessions.value[id]
    if (target.loaded) {
      applyFilters()
      return
    }
    await load(id)
  }
  async function load(id = active.value) {
    const target = sessions.value[id]
    if (!target || target.loading || disposed) return
    target.loading = true
    target.error = ''
    try {
      const result = await get(
        `${BASE}/chapters/${encodeURIComponent(id)}/questions`,
      )
      if (disposed) return
      target.entries = (result.items || []).map((item) => ({
        ...item,
        draft: item.attempt?.submitted
          ? item.attempt.feedback.submitted_answer
          : initialAnswer(item.question),
        submitting: false,
        marking: false,
        error: '',
      }))
      target.loaded = true
      if (active.value === String(id)) applyFilters()
    } catch (failure) {
      if (!disposed)
        target.error = errorText(failure, '本章题目加载失败，请重试。')
    } finally {
      target.loading = false
    }
  }
  function select(id) {
    if (visibleIds.value.includes(id)) selected.value = id
  }
  function move(offset) {
    const index = filtered.value.indexOf(current.value)
    const next = filtered.value[index + offset]
    if (next) select(next.question.id)
  }
  async function submit(entry) {
    if (
      disposed ||
      entry.submitting ||
      entry.attempt?.submitted ||
      !hasAnswer(entry.question, entry.draft)
    )
      return
    entry.submitting = true
    entry.error = ''
    try {
      if (!entry.attempt) {
        const attempt = await post(
          `${BASE}/questions/${encodeURIComponent(entry.question.id)}/attempts`,
          {},
        )
        if (
          attempt?.question?.id !== entry.question.id ||
          !attempt.id ||
          attempt.submitted
        )
          throw new Error('attempt mismatch')
        entry.attempt = attempt
      }
      const answer = Array.isArray(entry.draft) ? [...entry.draft] : entry.draft
      const result = await post(
        `${BASE}/attempts/${encodeURIComponent(entry.attempt.id)}/submit`,
        { answer },
      )
      if (disposed) return
      if (
        result?.id !== entry.attempt.id ||
        result?.question?.id !== entry.question.id ||
        !result.submitted
      )
        throw new Error('attempt mismatch')
      entry.attempt = result
      entry.draft = result.feedback.submitted_answer
      entry.attempted = true
      entry.ever_correct ||= result.feedback.correct === true
      onProgressChange()
    } catch (failure) {
      if (!disposed)
        entry.error = errorText(
          failure,
          '提交失败，请重试。已提交的答案以服务器首次记录为准。',
        )
    } finally {
      entry.submitting = false
    }
  }
  function retry(entry) {
    if (entry.submitting || !entry.attempt?.submitted) return
    entry.attempt = null
    entry.draft = initialAnswer(entry.question)
    entry.error = ''
  }
  async function toggleBookmark(entry) {
    if (disposed || entry.marking) return
    entry.marking = true
    entry.error = ''
    try {
      const result = await put(
        `${BASE}/bookmarks/${encodeURIComponent(entry.question.id)}`,
        { marked: !entry.marked },
      )
      if (disposed) return
      entry.marked = result.marked
      onProgressChange()
    } catch (failure) {
      if (!disposed) entry.error = errorText(failure, '标记保存失败，请重试。')
    } finally {
      entry.marking = false
    }
  }
  function dispose() {
    disposed = true
  }
  return {
    entries,
    filtered,
    current,
    selected,
    filters,
    loading,
    error,
    stats,
    setChapter,
    load,
    applyFilters,
    select,
    move,
    submit,
    retry,
    toggleBookmark,
    dispose,
  }
}
