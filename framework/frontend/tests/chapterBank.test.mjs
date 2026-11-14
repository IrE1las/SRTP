import test from 'node:test'
import assert from 'node:assert/strict'
import { createChapterQuestions } from '../src/features/chapterBank/useChapterQuestions.js'
import { formatReferenceValue, objectiveStats, referenceNotice, safeSourceUrl } from '../src/features/chapterBank/presentation.js'

function deferred() {
  let resolve, reject
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}

const listing = (id, total = 1) => ({ items: [{ id, stem: `题目 ${id}`, kind: 'choice' }], total })

test('reference values preserve false, zero, nested values and plain source text', () => {
  assert.equal(formatReferenceValue(false), '错误（否）')
  assert.equal(formatReferenceValue(true), '正确（是）')
  assert.equal(formatReferenceValue(0), '0')
  assert.equal(formatReferenceValue(['A', 'C']), 'A；C')
  assert.equal(formatReferenceValue({ signal: false, items: ['A', 'B'] }), 'signal：错误（否）\nitems：A；B')
  assert.equal(formatReferenceValue({}), '未提供')
  assert.equal(formatReferenceValue([]), '未提供')
  assert.equal(formatReferenceValue('  '), '未提供')
  assert.equal(formatReferenceValue('<img src=x onerror=alert(1)>'), '<img src=x onerror=alert(1)>')
})

test('unverified references remain explicit and objective stats never use combined ready counts', () => {
  for (const status of ['pending', 'partial', 'platform_answer']) {
    assert.match(referenceNotice(status), /待.*核验/)
  }
  assert.equal(referenceNotice('source_explicit'), '')
  assert.deepEqual(objectiveStats({ objective: 12, essay: 8, ready: 18, pending: 2 }), { total: 12, ready: null, pending: null })
  assert.deepEqual(objectiveStats({ objective: 12, objective_ready: 9, objective_pending: 3 }), { total: 12, ready: 9, pending: 3 })
  assert.equal(safeSourceUrl('javascript:alert(1)'), '')
  assert.equal(safeSourceUrl('/source-image.png'), '')
  assert.equal(safeSourceUrl('https://example.org/a'), 'https://example.org/a')
})

test('chapter and filter changes reset page and references, and stale listings cannot win', async () => {
  const calls = []
  const browser = createChapterQuestions({ get: (url, options) => {
    const task = deferred(); calls.push({ url, options, ...task }); return task.promise
  }, canViewReference: () => true })
  const first = browser.setChapter('1')
  calls[0].resolve(listing('first', 101)); await first
  const page = browser.setPage(3)
  assert.equal(calls[1].options.params.page, 3)
  calls[1].resolve(listing('page-three', 101)); await page
  const reference = browser.toggleReference('page-three')
  assert.equal(browser.references.value['page-three'].open, true)
  const filter = browser.setFilters({ kind: 'multi', pageSize: 50, search: '  课件  ' })
  assert.deepEqual(browser.references.value, {})
  assert.equal(browser.query.value.page, 1)
  assert.equal(calls[3].options.params.limit, 50)
  assert.equal(calls[3].options.params.search, '课件')
  const chapter = browser.setChapter('2')
  assert.equal(browser.query.value.kind, 'objective')
  assert.equal(browser.query.value.search, '')
  calls[4].resolve(listing('current')); await chapter
  calls[3].resolve(listing('old-filter')); await filter
  calls[2].resolve({ answer: '不应复现的旧答案' }); await reference
  assert.equal(browser.items.value[0].id, 'current')
  assert.deepEqual(browser.references.value, {})
  assert.equal(browser.loading.value, false)
})

test('students cannot request references, and role changes discard an in-flight answer', async () => {
  let role = 'student'
  const calls = []
  const answer = deferred()
  const browser = createChapterQuestions({ get: async (url) => {
    calls.push(url)
    return url.endsWith('/reference') ? answer.promise : listing('Q1')
  }, canViewReference: () => ['teacher', 'admin'].includes(role) })
  await browser.setChapter('1')
  await browser.toggleReference('Q1')
  assert.equal(calls.length, 1)
  assert.deepEqual(browser.references.value, {})
  role = 'teacher'
  await browser.toggleReference('not-in-this-list')
  assert.equal(calls.length, 1)
  const pending = browser.toggleReference('Q1')
  role = 'student'
  browser.clearReferences()
  answer.resolve({ answer: true }); await pending
  assert.deepEqual(browser.references.value, {})
})

test('list and reference failures expose retry without leaving loading stuck', async () => {
  let failList = true, failReference = true
  const browser = createChapterQuestions({ get: async (url) => {
    if (url.endsWith('/reference')) {
      if (failReference) throw new Error('offline')
      return { answer: false, answer_status: 'partial' }
    }
    if (failList) throw new Error('offline')
    return listing('Q2')
  }, canViewReference: () => true })
  await browser.setChapter('1')
  assert.match(browser.error.value, /加载失败/)
  assert.equal(browser.loading.value, false)
  failList = false; await browser.loadQuestions()
  assert.equal(browser.error.value, '')
  await browser.toggleReference('Q2')
  assert.match(browser.references.value.Q2.error, /加载失败/)
  failReference = false; await browser.loadReference('Q2')
  assert.equal(browser.references.value.Q2.data.answer, false)
  assert.equal(browser.references.value.Q2.error, '')
})

test('disposing invalidates outstanding list responses', async () => {
  const task = deferred()
  const browser = createChapterQuestions({ get: () => task.promise, canViewReference: () => false })
  const pending = browser.setChapter('1')
  browser.dispose()
  task.resolve(listing('disposed')); await pending
  assert.deepEqual(browser.items.value, [])
  assert.equal(browser.loading.value, false)
})
