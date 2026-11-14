import { ref } from 'vue'
import { errorText, QUESTION_KINDS } from './presentation.js'

// Kept local to the chapter bank: each list change invalidates its answer panels.
export function createChapterQuestions({ get, canViewReference }) {
  const query = ref({ chapterId: '', page: 1, pageSize: 20, kind: 'objective', status: 'all', search: '' })
  const items = ref([]), total = ref(0), loading = ref(false), error = ref('')
  const references = ref({})
  let listRequest = 0, referenceEpoch = 0, disposed = false

  function clearReferences() {
    referenceEpoch++
    references.value = {}
  }

  async function loadQuestions() {
    const serial = ++listRequest
    clearReferences()
    items.value = []
    total.value = 0
    error.value = ''
    loading.value = Boolean(query.value.chapterId) && !disposed
    if (!loading.value) return
    const { chapterId, page, pageSize, kind, status, search } = query.value
    try {
      const result = await get(`/chapter-bank/chapters/${encodeURIComponent(chapterId)}/questions`, {
        params: { page, limit: pageSize, kind, status, search },
      })
      if (serial !== listRequest || disposed) return
      items.value = Array.isArray(result?.items) ? result.items : []
      total.value = Number(result?.total) || 0
    } catch (failure) {
      if (serial === listRequest && !disposed) error.value = errorText(failure, '题目加载失败，请重试。')
    } finally {
      if (serial === listRequest && !disposed) loading.value = false
    }
  }

  function setChapter(chapterId) {
    query.value = { ...query.value, chapterId: String(chapterId || ''), page: 1, kind: 'objective', status: 'all', search: '' }
    return loadQuestions()
  }

  function setFilters(patch = {}) {
    const next = { ...query.value, page: 1 }
    if (QUESTION_KINDS.some(kind => kind.value === patch.kind)) next.kind = patch.kind
    if (['all', 'pending', 'answered'].includes(patch.status)) next.status = patch.status
    if ([20, 50, 100].includes(Number(patch.pageSize))) next.pageSize = Number(patch.pageSize)
    if (typeof patch.search === 'string') next.search = patch.search.trim()
    query.value = next
    return loadQuestions()
  }

  function setPage(page) {
    query.value = { ...query.value, page: Math.max(1, Math.floor(Number(page) || 1)) }
    return loadQuestions()
  }

  function referenceAllowed(id) {
    return !disposed && canViewReference() && items.value.some(item => item.id === id)
  }

  async function loadReference(id) {
    if (!referenceAllowed(id)) return
    if (!references.value[id]) references.value[id] = { open: true, loading: false, error: '', data: null }
    const entry = references.value[id]
    if (entry.loading) return
    const epoch = referenceEpoch
    entry.loading = true
    entry.error = ''
    try {
      const result = await get(`/chapter-bank/questions/${encodeURIComponent(id)}/reference`)
      if (epoch !== referenceEpoch || !referenceAllowed(id)) return
      entry.data = result
    } catch (failure) {
      if (epoch === referenceEpoch && referenceAllowed(id)) entry.error = errorText(failure, '参考资料加载失败，请重试。')
    } finally {
      if (epoch === referenceEpoch && referenceAllowed(id)) entry.loading = false
    }
  }

  function toggleReference(id) {
    if (!referenceAllowed(id)) return
    const entry = references.value[id]
    if (entry) {
      entry.open = !entry.open
      if (!entry.open || entry.loading || entry.data) return
    } else references.value[id] = { open: true, loading: false, error: '', data: null }
    return loadReference(id)
  }

  function dispose() {
    disposed = true
    listRequest++
    loading.value = false
    clearReferences()
  }

  return { query, items, total, loading, error, references, loadQuestions, setChapter, setFilters, setPage, toggleReference, loadReference, clearReferences, dispose }
}
