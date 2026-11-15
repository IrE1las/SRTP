import test from 'node:test'
import assert from 'node:assert/strict'
import { createChapterPractice, initialAnswer, hasAnswer, answerText, answerKeys } from '../src/features/chapterBank/useChapterPractice.js'

const attempt = (id, chapter = '1', kind = 'choice') => ({ id: `a-${id}`, question: { id, chapter, kind, stem: id, options: [{ key: 'A', text: '选项甲' }, { key: 'B', text: '选项乙' }] }, submitted: false, marked: false, feedback: null })
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }

test('answers support false, multiple choices and every required blank', () => {
  assert.equal(hasAnswer({ kind: 'true_false' }, false), true)
  assert.equal(hasAnswer({ kind: 'bool' }, null), false)
  assert.equal(hasAnswer({ kind: 'multi' }, []), false)
  assert.equal(hasAnswer({ kind: 'multi' }, ['B']), true)
  const question = { kind: 'cell', blank_count: 2 }
  assert.deepEqual(initialAnswer(question), ['', ''])
  assert.equal(hasAnswer(question, ['信号', ' ']), false)
  assert.equal(hasAnswer(question, ['信号', '联锁']), true)
  assert.equal(answerText({ kind: 'bool' }, false), '错误')
  assert.equal(answerText(attempt('q').question, ['B', 'A']), 'B．选项乙；A．选项甲')
})

test('previous and next retain drafts and feedback and draw only beyond history', async () => {
  let draws = 0
  const practice = createChapterPractice({ post: async (url, body) => {
    if (url.endsWith('/draw')) { draws++; return attempt(`q${draws}`) }
    return { ...attempt('q1'), submitted: true, feedback: { correct: false, submitted_answer: body.answer, correct_answer: 'B' } }
  }, put: async () => ({ marked: true }) })
  await practice.setChapter('1')
  practice.current.value.draft = 'A'
  await practice.submit()
  await practice.next()
  practice.current.value.draft = 'B'
  practice.previous()
  assert.equal(practice.current.value.attempt.submitted, true)
  assert.equal(practice.current.value.attempt.feedback.correct, false)
  await practice.next()
  assert.equal(practice.current.value.draft, 'B')
  assert.equal(draws, 2)
  await practice.setChapter('2')
  await practice.setChapter('1')
  assert.equal(practice.current.value.attempt.question.id, 'q2')
})

test('a slow chapter draw cannot overwrite a new chapter and double next draws once', async () => {
  const first = deferred(), second = deferred(); const calls = []
  const practice = createChapterPractice({ post: (url, body) => { calls.push({ url, body }); return calls.length === 1 ? first.promise : second.promise } })
  const old = practice.setChapter('1')
  const current = practice.setChapter('2')
  await practice.next()
  assert.equal(calls.length, 2)
  second.resolve(attempt('new', '2')); await current
  first.resolve(attempt('old')); await old
  assert.equal(practice.current.value.attempt.question.id, 'new')
  assert.equal(practice.busy.value, false)
})

test('submitting false sends a boolean and repeated clicks keep server first answer', async () => {
  const submitted = deferred(); let submits = 0; let sent
  const practice = createChapterPractice({ post: async (url, body) => {
    if (url.endsWith('/draw')) return attempt('bool', '1', 'bool')
    submits++; sent = body.answer; return submitted.promise
  } })
  await practice.setChapter('1'); practice.current.value.draft = false
  const one = practice.submit(); await practice.submit()
  assert.equal(sent, false); assert.equal(submits, 1)
  submitted.resolve({ ...attempt('bool', '1', 'bool'), submitted: true, feedback: { correct: true, submitted_answer: false, correct_answer: false } }); await one
  await practice.submit(); assert.equal(submits, 1)
  assert.equal(practice.current.value.draft, false)
})

test('late submit changes only its originating history entry', async () => {
  const response = deferred()
  const practice = createChapterPractice({ post: async (url) => url.endsWith('/submit') ? response.promise : attempt(url.includes('/1/') ? 'one' : 'two', url.includes('/1/') ? '1' : '2') })
  await practice.setChapter('1'); practice.current.value.draft = 'A'
  const pending = practice.submit(); await practice.setChapter('2')
  response.resolve({ ...attempt('one'), submitted: true, feedback: { correct: true, correct_answer: 'A' } }); await pending
  assert.equal(practice.current.value.attempt.question.id, 'two')
  assert.equal(practice.current.value.attempt.submitted, false)
  await practice.setChapter('1'); assert.equal(practice.current.value.attempt.submitted, true)
})

test('bookmarks persist via server, reject duplicate clicks, and marked practice is isolated', async () => {
  const response = deferred(); let puts = 0; const draws = []
  const practice = createChapterPractice({ post: async (url, body) => { draws.push(body); return attempt(`q${draws.length}`) }, put: async (url, body) => { puts++; assert.deepEqual(body, { marked: true }); return response.promise } })
  await practice.setChapter('1')
  const mark = practice.toggleBookmark(); await practice.toggleBookmark(); assert.equal(puts, 1)
  response.resolve({ question_id: 'q1', marked: true }); await mark
  assert.equal(practice.current.value.attempt.marked, true)
  await practice.setChapter('1', true); assert.equal(draws[1].bookmarked_only, true)
  await practice.setChapter('1', false); assert.equal(practice.current.value.attempt.question.id, 'q1')
})

test('random draw excludes history and a duplicate server response does not append', async () => {
  const bodies = []
  const practice = createChapterPractice({ post: async (url, body) => {
    if (url.endsWith('/submit')) return { ...attempt('same'), submitted: true, feedback: { correct: true, submitted_answer: 'A', correct_answer: 'A' } }
    bodies.push(body); return attempt('same')
  } })
  await practice.setChapter('1'); practice.current.value.draft = 'A'; await practice.submit(); await practice.next()
  assert.deepEqual(bodies[1].exclude_ids, ['same'])
  assert.equal(practice.history.value.length, 1)
  assert.match(practice.error.value, /重复/)
})

test('next waits for submission even when a draft has been filled', async () => {
  let draws = 0
  const practice = createChapterPractice({ post: async () => { draws++; return attempt('unanswered') } })
  await practice.setChapter('1'); await practice.next()
  practice.current.value.draft = 'A'; await practice.next()
  assert.equal(draws, 1)
})

test('an exhausted pool may repeat a question with a fresh attempt', async () => {
  let draws = 0
  const practice = createChapterPractice({ post: async url => {
    if (url.endsWith('/submit')) return { ...attempt('repeat'), submitted: true, feedback: { correct: true, submitted_answer: 'A' } }
    draws++; return { ...attempt('repeat'), id: draws === 1 ? 'a-repeat' : 'fresh-attempt' }
  } })
  await practice.setChapter('1'); practice.current.value.draft = 'A'; await practice.submit(); await practice.next()
  assert.equal(practice.history.value.length, 2)
  assert.equal(practice.current.value.attempt.id, 'fresh-attempt')
  assert.equal(practice.current.value.attempt.submitted, false)
})

test('a late submit response does not undo a bookmark saved during submission', async () => {
  const submitted = deferred()
  const practice = createChapterPractice({
    post: async url => url.endsWith('/submit') ? submitted.promise : attempt('marked'),
    put: async () => ({ question_id: 'marked', marked: true }),
  })
  await practice.setChapter('1'); practice.current.value.draft = 'A'
  const pending = practice.submit(); await practice.toggleBookmark()
  submitted.resolve({ ...attempt('marked'), submitted: true, feedback: { correct: true, submitted_answer: 'A' } }); await pending
  assert.equal(practice.current.value.attempt.marked, true)
})

test('compact source multi answer AC shows both option bodies and correct keys', () => {
  const question = { kind: 'multi', options: [{ key: 'A', text: '选项甲' }, { key: 'B', text: '选项乙' }, { key: 'C', text: '选项丙' }] }
  assert.deepEqual(answerKeys(question, 'AC'), ['A', 'C'])
  assert.deepEqual(answerKeys(question, ['A', 'C']), ['A', 'C'])
  assert.equal(answerText(question, 'AC'), 'A．选项甲；C．选项丙')
})
