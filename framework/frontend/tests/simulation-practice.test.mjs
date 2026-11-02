import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { computed, nextTick, ref } from 'vue'
import { parse } from '@vue/compiler-sfc'

async function consoleHarness({ saved = false, expired = false, refuseFullscreen = false } = {}) {
  const source = await readFile(new URL('../src/features/simulationConsole/TheorySimulationConsole.vue', import.meta.url), 'utf8')
  const script = parse(source).descriptor.scriptSetup.content.replace(/^import .*$/gm, '')
  const calls = [], events = new Map(), storage = new Map(), controls = { failReset: false }
  const key = 'free-practice-srtp-console-reference-7'
  if (saved) storage.set(key, 'saved-session')
  let mounted, unmount, sequence = 0
  let snap = { session_id: 'saved-session', version: 3, routes: [], sections: {}, switches: {}, interval_available: true }
  const client = {
    getStationPackage: async () => ({ station_name: '标准站', buttons: [], counts: {} }),
    createSimulationSession: async () => {
      calls.push('create')
      if (controls.failReset) throw new Error('offline')
      snap = { ...snap, session_id: 'practice-' + ++sequence, version: 0 }
      return snap
    },
    getSimulationSnapshot: async id => {
      calls.push(['snapshot', id])
      if (expired && id === 'saved-session') throw { response: { status: 409 } }
      return snap
    },
  }
  const document = {
    fullscreenElement: null,
    addEventListener: (name, fn) => events.set(name, fn),
    removeEventListener: name => events.delete(name),
    exitFullscreen: async () => {
      calls.push('exit-fullscreen')
      document.fullscreenElement = null
      events.get('fullscreenchange')()
    },
  }
  const deps = {
    computed, nextTick, ref, defineProps: () => ({ practice: true, questionKey: '' }),
    onMounted: fn => { mounted = fn }, onBeforeUnmount: fn => { unmount = fn },
    useUserStore: () => ({ user: { id: 7 } }),
    createPracticeConsoleClient: () => client,
    createTheoryConsoleClient: () => { throw new Error('Free practice must not open a question console') },
    COMMANDS: [], document, window: { setInterval: () => 1 }, clearInterval: () => {},
    ElMessage: { info: text => calls.push(['info', text]), error: text => calls.push(['error', text]) },
    sessionStorage: { getItem: key => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key) },
  }
  const state = new Function(...Object.keys(deps), script + '\nreturn {snapshot,loading,stale,consoleRoot,isFullscreen,toggleFullscreen,newSession};')(...Object.values(deps))
  const root = { requestFullscreen: async () => {
    calls.push('request-fullscreen')
    if (refuseFullscreen) throw new Error('Permission denied')
    document.fullscreenElement = state.consoleRoot.value
    events.get('fullscreenchange')()
  } }
  state.consoleRoot.value = root
  await mounted()
  return { state, calls, storage, document, events, controls, unmount }
}

test('free practice starts in a window; fullscreen, exit and Esc preserve the same station', async () => {
  const h = await consoleHarness()
  const current = h.state.snapshot.value
  assert.equal(h.state.isFullscreen.value, false)
  assert.deepEqual(h.calls, ['create'])
  await h.state.toggleFullscreen()
  assert.equal(h.state.isFullscreen.value, true)
  await h.state.toggleFullscreen()
  assert.equal(h.state.isFullscreen.value, false)
  await h.state.toggleFullscreen()
  h.document.fullscreenElement = null
  h.events.get('fullscreenchange')()
  assert.equal(h.state.isFullscreen.value, false)
  assert.equal(h.state.snapshot.value, current)
  assert.equal(h.calls.filter(c => c === 'create').length, 1)
  h.unmount()
  assert.equal(h.events.size, 0)
})

test('fullscreen refusal leaves free practice available in the current window', async () => {
  const h = await consoleHarness({ refuseFullscreen: true })
  await h.state.toggleFullscreen()
  assert.equal(h.state.isFullscreen.value, false)
  assert.equal(h.state.stale.value, false)
  assert.equal(h.state.snapshot.value.session_id, 'practice-1')
  assert.ok(h.calls.some(c => c[0] === 'info' && c[1].includes('可继续在当前窗口操作')))
  h.unmount()
})

test('refresh resumes only the practice session; expired sessions initialize afresh', async () => {
  const resumed = await consoleHarness({ saved: true })
  assert.deepEqual(resumed.calls, [['snapshot', 'saved-session']])
  assert.equal(resumed.state.snapshot.value.session_id, 'saved-session')
  resumed.unmount()
  const expired = await consoleHarness({ saved: true, expired: true })
  assert.deepEqual(expired.calls, [['snapshot', 'saved-session'], 'create'])
  assert.equal(expired.storage.get('free-practice-srtp-console-reference-7'), 'practice-1')
  expired.unmount()
})

test('reset needs a second explicit click and reports failure while keeping the current station', async () => {
  const h = await consoleHarness()
  await h.state.newSession()
  assert.equal(h.calls.filter(c => c === 'create').length, 1)
  await h.state.newSession()
  assert.equal(h.state.snapshot.value.session_id, 'practice-2')
  h.controls.failReset = true
  const current = h.state.snapshot.value
  await h.state.newSession()
  assert.equal(h.state.snapshot.value, current)
  await h.state.newSession()
  assert.equal(h.state.snapshot.value, current)
  assert.ok(h.calls.some(c => c[0] === 'error' && c[1].includes('重新初始化失败')))
  assert.equal(h.state.loading.value, false)
  h.unmount()
})
