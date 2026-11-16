import test from 'node:test'
import assert from 'node:assert/strict'
import {
  createChapterStudy,
  hasDraft,
} from '../src/features/chapterBank/useChapterStudy.js'

const question = (id, chapter = 1, kind = 'choice') => ({
  id,
  chapter,
  kind,
  stem: `题干 ${id}`,
  options: [
    { key: 'A', text: '甲' },
    { key: 'B', text: '乙' },
  ],
})
const item = (id, chapter = 1, kind = 'choice') => ({
  question: question(id, chapter, kind),
  attempted: false,
  ever_correct: false,
  marked: false,
  attempt: null,
})
const deferred = () => {
  let resolve
  const promise = new Promise((done) => {
    resolve = done
  })
  return { promise, resolve }
}
const makeStudy = (overrides = {}) =>
  createChapterStudy({
    get: async () => ({
      items: [item('one'), item('two'), item('three', 1, 'true_false')],
    }),
    ...overrides,
  })

test('partial blank answers and false are drafts, empty answers are not', () => {
  assert.equal(hasDraft(['已填写一空', '']), true)
  assert.equal(hasDraft(false), true)
  assert.equal(hasDraft(['', ' ']), false)
  assert.equal(hasDraft(null), false)
})

test('whole chapter loads without creating attempts, allows skipping and preserves drafts across chapters', async () => {
  let posts = 0
  const study = makeStudy({
    post: async () => {
      posts++
    },
  })
  await study.setChapter('1')
  assert.equal(study.filtered.value.length, 3)
  study.current.value.draft = 'B'
  study.move(1)
  assert.equal(study.current.value.question.id, 'two')
  study.select('three')
  study.move(-1)
  study.move(-1)
  assert.equal(study.current.value.draft, 'B')
  await study.setChapter('2')
  await study.setChapter('1')
  assert.equal(study.current.value.draft, 'B')
  assert.equal(posts, 0)
})

test('filters combine kind, history, bookmarks and search without discarding drafts', async () => {
  const study = makeStudy()
  await study.setChapter('1')
  const entry = study.entries.value[0]
  entry.marked = true
  entry.attempted = true
  entry.ever_correct = true
  entry.draft = 'A'
  study.applyFilters({ progress: 'unanswered' })
  assert.deepEqual(
    study.filtered.value.map((e) => e.question.id),
    ['two', 'three'],
  )
  study.applyFilters({ progress: 'not_correct', kind: 'true_false' })
  assert.deepEqual(
    study.filtered.value.map((e) => e.question.id),
    ['three'],
  )
  study.applyFilters({ progress: 'marked', kind: '', search: 'one' })
  assert.deepEqual(
    study.filtered.value.map((e) => e.question.id),
    ['one'],
  )
  study.applyFilters({ search: '不存在' })
  assert.equal(study.filtered.value.length, 0)
  study.applyFilters({ progress: '', search: '' })
  assert.equal(study.entries.value[0].draft, 'A')
})

test('slow chapter response cannot replace active chapter and cached response remains usable', async () => {
  const slow = deferred()
  const study = makeStudy({
    get: (url) =>
      url.includes('/1/')
        ? slow.promise
        : Promise.resolve({ items: [item('chapter-two', 2)] }),
  })
  const pending = study.setChapter('1')
  await study.setChapter('2')
  slow.resolve({ items: [item('chapter-one')] })
  await pending
  assert.equal(study.current.value.question.id, 'chapter-two')
  await study.setChapter('1')
  assert.equal(study.current.value.question.id, 'chapter-one')
})

test('submit creates only selected attempt, prevents double submit and keeps feedback visible in unanswered filter', async () => {
  const pending = deferred(),
    calls = []
  const study = makeStudy({
    post: async (url, body) => {
      calls.push({ url, body })
      return url.endsWith('/attempts')
        ? { id: 'attempt-one', question: question('one'), submitted: false }
        : pending.promise
    },
  })
  await study.setChapter('1')
  study.applyFilters({ progress: 'unanswered' })
  const entry = study.current.value
  entry.draft = 'A'
  const first = study.submit(entry)
  await study.submit(entry)
  study.move(1)
  pending.resolve({
    id: 'attempt-one',
    question: question('one'),
    submitted: true,
    feedback: { correct: true, submitted_answer: 'A', correct_answer: 'A' },
  })
  await first
  assert.equal(calls.length, 2)
  assert.equal(study.current.value.question.id, 'two')
  assert.equal(entry.ever_correct, true)
  assert.equal(study.filtered.value.length, 3)
  study.applyFilters({ progress: 'unanswered' })
  assert.equal(study.filtered.value.length, 2)
  study.retry(entry)
  assert.equal(entry.attempt, null)
  assert.equal(entry.draft, null)
  assert.equal(entry.ever_correct, true)
})

test('failed submission retries the same attempt and false remains a boolean', async () => {
  let starts = 0,
    submits = 0
  const study = makeStudy({
    post: async (url, body) => {
      if (url.endsWith('/attempts')) {
        starts++
        return {
          id: 'boolean-attempt',
          question: question('three', 1, 'true_false'),
        }
      }
      assert.equal(body.answer, false)
      if (++submits === 1) throw new Error('network')
      return {
        id: 'boolean-attempt',
        question: question('three', 1, 'true_false'),
        submitted: true,
        feedback: {
          correct: false,
          submitted_answer: false,
          correct_answer: true,
        },
      }
    },
  })
  await study.setChapter('1')
  study.select('three')
  const entry = study.current.value
  entry.draft = false
  await study.submit(entry)
  assert.match(entry.error, /提交失败/)
  await study.submit(entry)
  assert.equal(starts, 1)
  assert.equal(entry.attempted, true)
  assert.equal(entry.ever_correct, false)
})

test('restores submitted feedback and bookmarks and offers empty marked-only state', async () => {
  const saved = {
    ...item('saved'),
    attempted: true,
    ever_correct: true,
    marked: true,
    attempt: {
      id: 'saved-attempt',
      submitted: true,
      feedback: { correct: true, submitted_answer: 'B' },
    },
  }
  const study = makeStudy({
    get: async () => ({ items: [saved, item('new')] }),
    put: async () => ({ marked: false }),
  })
  await study.setChapter('1', true)
  assert.equal(study.filtered.value.length, 1)
  assert.equal(study.current.value.draft, 'B')
  await study.toggleBookmark(study.current.value)
  study.applyFilters({ progress: 'marked' })
  assert.equal(study.filtered.value.length, 0)
})
