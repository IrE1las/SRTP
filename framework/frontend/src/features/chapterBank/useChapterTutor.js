import { computed, ref } from 'vue'
import { errorText } from './presentation.js'

const path = (id) =>
  `/chapter-bank/practice/attempts/${encodeURIComponent(id)}/ai-chat`
export function createChapterTutor({
  get,
  post,
  makeId = () => crypto.randomUUID(),
  schedule = (fn, delay) => setTimeout(fn, delay),
  cancel = (id) => clearTimeout(id),
}) {
  const sessions = ref({}),
    active = ref('')
  const state = computed(() => sessions.value[active.value] || null)
  let disposed = false,
    poll = null
  function stopPoll() {
    if (poll !== null) cancel(poll)
    poll = null
  }
  function update(target, result) {
    target.turns = result.turns || []
    target.revision = result.revision
    target.configured = result.configured
    target.generating = result.generating
    target.maxTurns = result.max_turns || 20
    target.loaded = true
    if (
      target.pending &&
      target.turns.some((turn) => turn.id === target.pending.request_id)
    ) {
      if (
        target.pending.action === 'ask' &&
        target.draft.trim() === target.pending.message
      )
        target.draft = ''
      target.pending = null
    }
  }
  async function load(id = active.value) {
    const target = sessions.value[id]
    if (!target || disposed || target.loading || target.sending) return
    target.loading = true
    target.error = ''
    try {
      const result = await get(path(id))
      if (!disposed) {
        update(target, result)
        if (target.pending && !target.generating) target.error = '上一轮回答尚未确认，请重试本轮。'
      }
    } catch (failure) {
      if (!disposed)
        target.error = errorText(failure, 'AI对话加载失败，请重试。')
    } finally {
      target.loading = false
      if (!disposed && active.value === id && target.generating) {
        stopPoll()
        poll = schedule(() => load(id), 2500)
      }
    }
  }
  async function setAttempt(id) {
    stopPoll()
    active.value = String(id || '')
    if (!active.value || disposed) return
    if (!sessions.value[id])
      sessions.value[id] = {
        turns: [],
        revision: 0,
        configured: false,
        generating: false,
        loaded: false,
        loading: false,
        sending: false,
        error: '',
        draft: '',
        pending: null,
        maxTurns: 20,
      }
    await load(id)
  }
  async function send(action = 'ask', message = null) {
    const id = active.value,
      target = state.value
    if (
      !target ||
      disposed ||
      target.sending ||
      target.loading ||
      target.generating ||
      !target.loaded ||
      !target.configured
    )
      return
    if (target.turns.length >= target.maxTurns) return
    if (!target.pending) {
      const value = message == null ? target.draft.trim() : message.trim()
      if (action === 'ask' && (!value || value.length > 1500)) return
      target.pending = {
        request_id: makeId(),
        revision: target.revision,
        action,
        message: action === 'explain' ? '' : value,
      }
    }
    target.sending = true
    target.error = ''
    try {
      const result = await post(
        path(id),
        { ...target.pending },
        { timeout: 120000 },
      )
      if (!disposed) update(target, result)
    } catch (failure) {
      if (!disposed) {
        target.error = errorText(
          failure,
          'AI回答暂未确认，请重试本轮；已完成的回答不会重复保存。',
        )
        // A revision conflict requires reloading before allowing a different question.
        if (failure?.response?.status === 409) {
          const previousRevision = target.revision
          try {
            const result = await get(path(id))
            if (!disposed) {
              update(target, result)
              if (result.revision !== previousRevision) target.pending = null
            }
          } catch {
            /* Keep the original input and pending request for a safe retry. */
          }
        }
      }
    } finally {
      target.sending = false
      if (!disposed && active.value === id && target.generating) {
        stopPoll()
        poll = schedule(() => load(id), 2500)
      }
    }
  }
  function dispose() {
    disposed = true
    stopPoll()
  }
  return { state, setAttempt, load, send, dispose }
}
