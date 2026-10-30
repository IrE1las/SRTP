import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { parse } from '@vue/compiler-sfc'
import { computed, reactive, ref } from 'vue'
import { gradeStates, gradeActions, gradeError, gradePayload } from '../src/domain/examGrades.js'
import { beijingTime, examError, examStates } from '../src/domain/exams.js'

async function harness(options = {}) {
  const source = await readFile(new URL('../src/views/teacher/ExamAttempt.vue', import.meta.url), 'utf8')
  const descriptor = parse(source).descriptor, calls = [], guards = {}, route = { params: { attemptId: 'sid' } }
  let current = { revision: 0, status: 'ungraded', score: null, comment: null, published: null, publications: [], audit: [], ...options.grade }
  const deps = {
    computed, reactive, ref, watch: () => {}, onBeforeUnmount: () => {},
    useRoute: () => route, onBeforeRouteLeave: fn => { guards.leave = fn }, onBeforeRouteUpdate: fn => { guards.update = fn },
    window: { addEventListener: () => {}, removeEventListener: () => {} },
    ElMessageBox: { confirm: async () => { if (options.cancel) throw new Error('cancel') } },
    getExamAttempt: async sid => {
      calls.push({ action: 'get', sid })
      if (sid !== 'sid') throw new Error('not found')
      return { session_id: sid, exam_id: 1, status: 'submitted', identity: {}, control_events: [], grade: structuredClone(current) }
    },
    saveExamGrade: async (sid, body) => {
      calls.push({ action: 'save', sid, body: structuredClone(body) })
      if (options.conflict) throw { response: { data: { detail: '成绩已被修改，请保留本地输入并刷新核对' } } }
      current = { ...current, revision: current.revision + 1, status: 'draft', score: body.score == null ? null : Number(body.score), comment: body.comment }
      return structuredClone(current)
    },
    confirmExamGrade: async (sid, revision) => { calls.push({ action: 'confirm', sid, revision }); current = { ...current, revision: revision + 1, status: 'confirmed' }; return structuredClone(current) },
    publishExamGrade: async (sid, revision) => {
      calls.push({ action: 'publish', sid, revision })
      if (options.failPublish) throw new Error('lost response')
      current = { ...current, revision: revision + 1, status: 'published', published: { score: current.score, comment: current.comment, version: (current.published?.version || 0) + 1 } }
      return structuredClone(current)
    },
    downloadExam: async () => {}, gradeStates, gradeActions, gradeError, gradePayload, beijingTime, examError, examStates,
  }
  const script = descriptor.scriptSetup.content.replace(/^import .*$/gm, '')
  const state = new Function(...Object.keys(deps), script + '\nreturn {data,grade,form,dirty,working,notice,success,load,refresh,save,confirm,publish,beforeUnload,scoreError,hasScore};')(...Object.values(deps))
  await state.load()
  return { state, calls, guards, route }
}

test('manual grade page saves, confirms and publishes in three independent actions, including zero', async () => {
  const { state, calls } = await harness()
  await state.confirm(); await state.publish()
  assert.equal(calls.filter(c => c.action !== 'get').length, 0)
  state.form.score = '0'; state.form.comment = '独立评语'
  await state.publish()
  assert.equal(state.dirty.value, true)
  await state.save()
  assert.equal(state.grade.value.status, 'draft')
  assert.equal(state.grade.value.published, null)
  assert.deepEqual(calls.at(-1).body, { revision: 0, score: '0', comment: '独立评语' })
  await state.publish()
  assert.equal(calls.at(-1).action, 'save')
  await state.confirm()
  assert.equal(state.grade.value.status, 'confirmed')
  assert.equal(state.grade.value.published, null)
  assert.equal(calls.at(-1).revision, 1)
  await state.publish()
  assert.equal(calls.at(-1).revision, 2)
  assert.equal(state.grade.value.published.score, 0)
  assert.equal(state.grade.value.published.version, 1)
})

test('unsaved corrections block confirmation and publication; old published version stays visible', async () => {
  const { state, calls } = await harness({ grade: { revision: 3, status: 'published', score: 70, published: { score: 70, version: 1 } } })
  state.form.score = '91.50'
  await state.confirm(); await state.publish()
  assert.equal(calls.length, 1)
  await state.save()
  assert.equal(state.grade.value.score, 91.5)
  assert.equal(state.grade.value.published.score, 70)
  assert.equal(state.grade.value.published.version, 1)
  await state.confirm(); await state.publish()
  assert.equal(state.grade.value.published.score, 91.5)
  assert.equal(state.grade.value.published.version, 2)
})

test('revision conflict preserves entered score and comment and cannot silently confirm a stale draft', async () => {
  const { state, calls } = await harness({ conflict: true })
  state.form.score = '88.88'; state.form.comment = '保留输入'
  await state.save(); await state.confirm(); await state.publish()
  assert.equal(state.form.score, '88.88')
  assert.equal(state.form.comment, '保留输入')
  assert.equal(state.dirty.value, true)
  assert.match(state.notice.value, /成绩已被修改/)
  assert.deepEqual(calls.map(c => c.action), ['get', 'save'])
})

test('missing or invalid scores cannot confirm; empty score can remain a comment-only draft', async () => {
  const { state, calls } = await harness()
  state.form.comment = '待复核'
  await state.save(); await state.confirm()
  assert.equal(calls.at(-1).body.score, null)
  assert.equal(state.hasScore.value, false)
  state.form.score = '100.001'
  await state.save(); await state.confirm(); await state.publish()
  assert.deepEqual(calls.map(c => c.action), ['get', 'save'])
  assert.match(state.scoreError.value, /两位小数/)
})

test('cancelled refresh and route navigation retain unsaved inputs; native reload gets a warning', async () => {
  const { state, calls, guards } = await harness({ cancel: true })
  state.form.score = '80'
  await state.refresh()
  assert.equal(await guards.leave(), false)
  assert.equal(await guards.update(), false)
  assert.equal(state.form.score, '80')
  assert.equal(calls.length, 1)
  let prevented = false
  state.beforeUnload({ preventDefault: () => { prevented = true } })
  assert.equal(prevented, true)
})

test('failed or cancelled publication never claims success or clears the confirmed version', async () => {
  for (const options of [{ cancel: true }, { failPublish: true }]) {
    const { state } = await harness({ ...options, grade: { revision: 2, status: 'confirmed', score: 80 } })
    await state.publish()
    assert.equal(state.grade.value.status, 'confirmed')
    assert.equal(state.grade.value.published, null)
    assert.equal(state.success.value, '')
    assert.equal(state.working.value, false)
  }
})

test('failed route load clears old answer so it cannot be mistaken for the new student', async () => {
  const { state, route } = await harness({ grade: { revision: 3, status: 'published', score: 80 } })
  route.params.attemptId = 'forbidden'
  await state.load()
  assert.equal(state.data.value, null)
  assert.equal(state.form.score, '')
  assert.equal(state.dirty.value, false)
})

test('decimal input preserves precision without rounding and never converts a blank into zero', () => {
  for (const valid of ['', '0', '0.01', '83.25', '100.00']) assert.equal(gradeError(valid), '')
  for (const invalid of ['-1', '100.01', '1.001', '1.230', 'NaN', 'Infinity', '1e2']) assert.notEqual(gradeError(invalid), '')
  assert.deepEqual(gradePayload({ score: '', comment: ' ' }, 0), { revision: 0, score: null, comment: null })
  assert.equal(gradePayload({ score: '99.99', comment: '' }, 4).score, '99.99')
})
