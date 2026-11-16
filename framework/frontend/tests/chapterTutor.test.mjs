import test from 'node:test'
import assert from 'node:assert/strict'
import { createChapterTutor } from '../src/features/chapterBank/useChapterTutor.js'

const response = (turns = [], extra = {}) => ({
  turns,
  revision: turns.length,
  configured: true,
  generating: false,
  max_turns: 20,
  ...extra,
})
const turn = (id = 'request-1', action = 'explain', question = '本题详解') => ({
  id,
  action,
  question,
  answer: '这是铁路专业讲解。',
  status: 'answered',
  sources: [],
})
const deferred = () => {
  let resolve, reject
  const promise = new Promise((done, fail) => {
    resolve = done
    reject = fail
  })
  return { promise, resolve, reject }
}

test('unsubmitted questions never fetch AI context; restored conversations are isolated by attempt', async () => {
  const calls = []
  const tutor = createChapterTutor({
    get: async (url) => {
      calls.push(url)
      return response()
    },
  })
  await tutor.setAttempt('')
  assert.equal(calls.length, 0)
  await tutor.setAttempt('one')
  tutor.state.value.draft = '为什么？'
  await tutor.setAttempt('two')
  assert.equal(tutor.state.value.draft, '')
  await tutor.setAttempt('one')
  assert.equal(tutor.state.value.draft, '为什么？')
})

test('initial explanation posts only identity, revision and action and duplicate clicks send once', async () => {
  const pending = deferred(),
    calls = []
  const tutor = createChapterTutor({
    get: async () => response(),
    makeId: () => 'request-1',
    post: async (...args) => {
      calls.push(args)
      return pending.promise
    },
  })
  await tutor.setAttempt('one')
  const first = tutor.send('explain')
  await tutor.send('explain')
  assert.equal(calls.length, 1)
  assert.deepEqual(calls[0][1], {
    request_id: 'request-1',
    revision: 0,
    action: 'explain',
    message: '',
  })
  assert.equal(calls[0][2].timeout, 120000)
  pending.resolve(response([turn()]))
  await first
  assert.equal(tutor.state.value.turns.length, 1)
  assert.equal(tutor.state.value.pending, null)
})

test('late answer updates only the original attempt and survives switching back', async () => {
  const pending = deferred()
  let saved = response()
  const tutor = createChapterTutor({
    get: async (url) => (url.includes('/one/') ? saved : response()),
    post: () => pending.promise,
    makeId: () => 'request-1',
  })
  await tutor.setAttempt('one')
  const first = tutor.send('explain')
  await tutor.setAttempt('two')
  saved = response([turn()])
  pending.resolve(saved)
  await first
  assert.equal(tutor.state.value.turns.length, 0)
  await tutor.setAttempt('one')
  assert.equal(tutor.state.value.turns[0].id, 'request-1')
  tutor.dispose()
})

test('network retry reuses the request id and body without clearing the students question', async () => {
  const calls = []
  const tutor = createChapterTutor({
    get: async () => response(),
    makeId: () => 'request-1',
    post: async (url, body) => {
      calls.push(body)
      if (calls.length === 1) throw new Error('network')
      return response([turn('request-1', 'ask', '为什么不能选A？')])
    },
  })
  await tutor.setAttempt('one')
  tutor.state.value.draft = '为什么不能选A？'
  await tutor.send()
  assert.equal(tutor.state.value.draft, '为什么不能选A？')
  assert.ok(tutor.state.value.error)
  await tutor.send()
  assert.deepEqual(calls[0], calls[1])
  assert.equal(tutor.state.value.pending, null)
  assert.equal(tutor.state.value.draft, '')
})

test('revision conflict reloads history while preserving the unsent question', async () => {
  let loads = 0
  const tutor = createChapterTutor({
    get: async () =>
      ++loads === 1 ? response() : response([turn('other-tab')]),
    makeId: () => 'request-1',
    post: async () => {
      throw { response: { status: 409, data: { detail: '已有更新' } } }
    },
  })
  await tutor.setAttempt('one')
  tutor.state.value.draft = '道岔表示是什么意思？'
  await tutor.send()
  assert.equal(tutor.state.value.revision, 1)
  assert.equal(tutor.state.value.pending, null)
  assert.equal(tutor.state.value.draft, '道岔表示是什么意思？')
})

test('unconfigured, empty, oversized and capped conversations cannot launch generation', async () => {
  let posts = 0
  const tutor = createChapterTutor({
    get: async () => response([], { configured: false }),
    post: async () => {
      posts++
    },
  })
  await tutor.setAttempt('one')
  await tutor.send('explain')
  tutor.state.value.configured = true
  await tutor.send()
  tutor.state.value.draft = '字'.repeat(1501)
  await tutor.send()
  tutor.state.value.turns = Array.from({ length: 20 }, () => turn())
  await tutor.send('explain')
  assert.equal(posts, 0)
})

test('another tabs active generation is polled and changing questions cancels its timer', async () => {
  const scheduled = [],
    cancelled = []
  const tutor = createChapterTutor({
    get: async () => response([], { generating: true }),
    schedule: (fn) => {
      scheduled.push(fn)
      return scheduled.length
    },
    cancel: (id) => cancelled.push(id),
  })
  await tutor.setAttempt('one')
  assert.equal(scheduled.length, 1)
  await tutor.setAttempt('')
  assert.deepEqual(cancelled, [1])
  tutor.dispose()
})

test('load failure offers retry; disposal prevents an old response from appearing', async () => {
  let loads = 0
  const pending = deferred()
  const tutor = createChapterTutor({
    get: async () => {
      if (++loads === 1) throw new Error('network')
      return pending.promise
    },
  })
  await tutor.setAttempt('one')
  assert.ok(tutor.state.value.error)
  const retry = tutor.load()
  tutor.dispose()
  pending.resolve(response([turn()]))
  await retry
  assert.equal(tutor.state.value.turns.length, 0)
})

test('switching away after a failed first explanation keeps the retry action available on return', async () => {
  const tutor = createChapterTutor({ get: async () => response(), makeId: () => 'request-1',
    post: async () => { throw new Error('network') } })
  await tutor.setAttempt('one'); await tutor.send('explain')
  await tutor.setAttempt('two'); await tutor.setAttempt('one')
  assert.equal(tutor.state.value.pending.request_id, 'request-1')
  assert.match(tutor.state.value.error, /重试本轮/)
})
