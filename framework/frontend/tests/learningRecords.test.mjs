import test from 'node:test'
import assert from 'node:assert/strict'
import { createLearningRecords, scoreText, operationLabel, feedbackLabel } from '../src/features/learningRecords/useLearningRecords.js'

const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no }); return { promise, resolve, reject } }
const entry = (id, kind = 'lab') => ({ key: `${kind}:${id}`, record_id: id, kind, title: `实验 ${id}` })

test('record scores preserve zero and distinguish ungraded, pending and true scores', () => {
  assert.equal(scoreText({ score: 0, score_max: 100 }), '0 / 100 分')
  assert.equal(scoreText({ score: null, score_label: '未评分' }), '未评分')
  assert.equal(scoreText({ score: null, score_label: '待教师评阅' }), '待教师评阅')
  assert.equal(operationLabel('SWITCH_SINGLE_LOCK'), '道岔单锁')
  assert.equal(feedbackLabel('ai'), 'AI教学解析')
  assert.equal(feedbackLabel('rules'), '规则教学反馈')
})

test('a late list cannot replace the chosen kind and filters restart pagination', async () => {
  const first = deferred(), second = deferred(), calls = []
  const records = createLearningRecords({ get: (url, config) => { calls.push(config.params); return calls.length === 1 ? first.promise : second.promise } })
  const old = records.load()
  const latest = records.setKind('lab')
  second.resolve({ items: [entry('new', 'lab')], total: 1, counts: { all: 3, lab: 1 } }); await latest
  first.resolve({ items: [entry('old')], total: 9, counts: { all: 9 } }); await old
  assert.equal(records.items.value[0].record_id, 'new')
  assert.equal(records.kind.value, 'lab')
  assert.equal(records.total.value, 1)
  assert.equal(records.loading.value, false)
  assert.equal(calls[1].page, 1)
  assert.equal(calls[1].kind, 'lab')
})

test('late detail and detail errors belong only to the currently opened record', async () => {
  const first = deferred(), second = deferred()
  const records = createLearningRecords({ get: url => url.endsWith('/a') ? first.promise : second.promise })
  const old = records.open(entry('a')), current = records.open(entry('b'))
  second.resolve({ ...entry('b'), errors: [], operations: [], feedback: [] }); await current
  first.reject(new Error('old request failed')); await old
  assert.equal(records.detail.value.record_id, 'b')
  assert.equal(records.detailError.value, '')
  assert.equal(records.detailLoading.value, false)
  records.close()
  assert.equal(records.selected.value, null)
})

test('list failures allow retry and disposing prevents outstanding data from resurfacing', async () => {
  let call = 0
  const records = createLearningRecords({ get: async () => { if (!call++) throw new Error('network'); return { items: [entry('ok')], total: 1, counts: {} } } })
  await records.load(); assert.ok(records.error.value); assert.equal(records.loading.value, false)
  await records.load(); assert.equal(records.error.value, ''); assert.equal(records.items.value[0].record_id, 'ok')
  const pending = deferred(), disposed = createLearningRecords({ get: () => pending.promise })
  const work = disposed.open(entry('a')); disposed.dispose(); pending.resolve(entry('a')); await work
  assert.equal(disposed.detail.value, null)
})
