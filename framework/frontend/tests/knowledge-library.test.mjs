import test from 'node:test'
import assert from 'node:assert/strict'
import { useKnowledgeLibrary } from '../src/features/knowledge/useKnowledgeLibrary.js'

const doc = (id, title = id, enabled = true) => ({
  id,
  title,
  description: '',
  filename: `${id}.md`,
  enabled,
  revision: 1,
  status: 'ready',
  pages: [{ location: '第1段', text: title }],
})
test('library ignores stale selection responses and preserves changes after failed save', async () => {
  const waiting = new Map()
  const state = useKnowledgeLibrary({
    getMaterial: (id) => new Promise((resolve) => waiting.set(id, resolve)),
    editMaterial: async () => {
      throw new Error('conflict')
    },
  })
  const first = state.select('first'),
    second = state.select('second')
  waiting.get('second')(doc('second'))
  await second
  waiting.get('first')(doc('first'))
  await first
  assert.equal(state.selected.value.id, 'second')
  state.form.title = 'edited'
  await assert.rejects(state.save(), /conflict/)
  assert.equal(state.form.title, 'edited')
  assert.equal(state.selected.value.title, 'second')
  assert.equal(state.dirty.value, true)
  assert.equal(state.saving.value, false)
})

test('save carries revision and enable changes; deleting last source clears preview', async () => {
  let rows = [doc('course')],
    changed
  const state = useKnowledgeLibrary({
    listMaterials: async () => rows,
    getMaterial: async () => rows[0],
    editMaterial: async (id, body) => {
      changed = body
      return { ...rows[0], ...body, revision: 2 }
    },
    deleteMaterial: async (id, revision) => {
      assert.equal(revision, 2)
      rows = []
      return { message: 'removed' }
    },
  })
  await state.reload()
  state.form.enabled = false
  await state.save()
  assert.equal(changed.revision, 1)
  assert.equal(state.selected.value.enabled, false)
  assert.equal(state.dirty.value, false)
  await state.remove()
  assert.equal(state.selected.value, null)
  assert.equal(state.currentPage.value, null)
})

test('search and visibility filters distinguish unusable text from enabled materials', () => {
  const state = useKnowledgeLibrary({})
  state.documents.value = [
    doc('a', '道岔'),
    doc('b', '轨道电路', false),
    { ...doc('c', '扫描稿'), status: 'needs_text' },
  ]
  state.filter.value = 'enabled'
  assert.deepEqual(
    state.filtered.value.map((d) => d.id),
    ['a'],
  )
  state.filter.value = 'disabled'
  assert.deepEqual(
    state.filtered.value.map((d) => d.id),
    ['b', 'c'],
  )
  state.query.value = '轨道'
  assert.deepEqual(
    state.filtered.value.map((d) => d.id),
    ['b'],
  )
})
