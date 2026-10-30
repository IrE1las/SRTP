import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { computed, ref } from 'vue'
import { parse } from '@vue/compiler-sfc'
import { ExamJournal, beijingTime, secondsLeft, clockText, completedMessage, examError } from '../src/domain/exams.js'

const sample = values => ({session_id:'sid', exam_id:1, name:'考试', status:'active', revision:0, server_now:'2030-01-02T04:00:00Z', deadline:'2030-01-02T04:05:00Z', exit_count:0, fullscreen_state:'inside', question:{title:'调车',prompt:'D3到D7'}, console:{session_id:'sid',revision:2,status:'active',events:[]}, ...values})
async function harness(options = {}) {
  const source = await readFile(new URL('../src/views/student/ExamAttempt.vue', import.meta.url), 'utf8')
  const descriptor = parse(source).descriptor, calls = [], storage = new Map(), guards = {}
  let current = sample(options.initial)
  const invoke = (name, fn) => async (...args) => { calls.push({name,args:structuredClone(args)}); return fn(...args) }
  const document = {fullscreenElement:{}, documentElement:{requestFullscreen:invoke('requestFullscreen',async()=>{})}, exitFullscreen:invoke('exitFullscreen',async()=>{document.fullscreenElement=null}), addEventListener:()=>{},removeEventListener:()=>{}}
  const navigator = {onLine:true}
  const deps = {
    computed, ref, ExamJournal, beijingTime, secondsLeft, clockText, completedMessage, examError,
    useRoute:() => ({params:{attemptId:'sid'},query:{}}), onMounted:()=>{},onBeforeUnmount:()=>{},onBeforeRouteLeave:fn=>{guards.leave=fn},onBeforeRouteUpdate:fn=>{guards.update=fn},
    document,navigator,window:{addEventListener:()=>{},removeEventListener:()=>{}},performance,
    localStorage:{getItem:key=>storage.get(key)??null,setItem:(key,value)=>storage.set(key,value)},
    getExamAttempt:invoke('get',async()=>structuredClone(current)),
    syncExam:invoke('sync',options.sync || (async(id,body)=>({...structuredClone(current),acknowledged_events:body.events.map(e=>e.event_id)}))),
    submitExam:invoke('submit',options.submit || (async()=>{current=sample({...current,status:'submitted',revision:1,finish_reason:'manual',message:completedMessage,console:{...current.console,status:'submitted'}});return current})),
    examStation:async()=>({}),examEvent:invoke('event',async()=>current.console),downloadExam:invoke('download',async()=>{}),
    reportExamExit:invoke('keepalive',async()=>{}),
    setInterval:()=>1,clearInterval:()=>{},
  }
  const script = descriptor.scriptSetup.content.replace(/^import .*$/gm, '')
  const state = new Function(...Object.keys(deps), script + '\nreturn {attempt,consoleRef,notice,paused,connected,pending,submitting,refreshing,estimatedNow,initialize,synchronize,refreshExam,submit,accept,observeFullscreen,offline,online,beforeUnload,consoleApi};')(...Object.values(deps))
  await state.initialize()
  return {state,calls,guards,document,navigator,source,storage}
}

test('actual exam page waits for acknowledged click flush before submitting its exact sequence', async () => {
  const {state,calls,guards} = await harness()
  let release
  const gate = new Promise(resolve=>{release=resolve})
  state.consoleRef.value={flush:()=>gate}
  const pending=state.submit()
  assert.equal(state.submitting.value,true)
  assert.ok(!calls.some(c=>c.name==='submit'))
  release({revision:2})
  await pending
  assert.deepEqual(calls.find(c=>c.name==='submit').args,['sid',2])
  assert.equal(state.attempt.value.status,'submitted')
  assert.equal(calls.filter(c=>c.name==='exitFullscreen').length,1)
  assert.equal(await guards.leave(),true)
  const count=calls.filter(c=>c.name==='sync').length
  state.observeFullscreen()
  assert.equal(calls.filter(c=>c.name==='sync').length,count)
})

test('unconfirmed click and failed submission never display completed state', async () => {
  const first=await harness()
  first.state.consoleRef.value={flush:async()=>{throw new Error('unconfirmed')}}
  await first.state.submit()
  assert.ok(!first.calls.some(c=>c.name==='submit'))
  assert.equal(first.state.attempt.value.status,'active')
  const lost=await harness({submit:async()=>{throw new Error('lost response')}})
  lost.state.consoleRef.value={flush:async()=>({revision:2})}
  await lost.state.submit()
  assert.equal(lost.state.attempt.value.status,'active')
  assert.ok(!lost.calls.some(c=>c.name==='exitFullscreen'))
  await lost.state.accept(sample({status:'submitted',revision:2,finish_reason:'manual'}))
  assert.equal(lost.state.attempt.value.status,'submitted')
})

test('offline pauses actual operation calls, captures fullscreen exit durably, then replays original event', async () => {
  const {state,calls,document,navigator,storage}=await harness()
  navigator.onLine=false;state.offline()
  await assert.rejects(state.consoleApi.event('sid',{}),/暂停/)
  assert.ok(!calls.some(c=>c.name==='event'))
  document.fullscreenElement=null;state.observeFullscreen()
  const stored=JSON.parse(storage.get('srtp-exam-control-sid'))
  assert.equal(stored.pending[0].kind,'exit')
  assert.equal(state.paused.value,true)
  navigator.onLine=true
  await state.synchronize()
  const body=calls.filter(c=>c.name==='sync').at(-1).args[1]
  assert.deepEqual(body.events,stored.pending)
  assert.equal(body.fullscreen,false)
})

test('expiry pauses the page immediately, and stale responses cannot reopen a sealed attempt', async () => {
  const {state}=await harness()
  state.estimatedNow.value=Date.parse(state.attempt.value.deadline)
  assert.equal(state.paused.value,true)
  await assert.rejects(state.consoleApi.event('sid',{}),/暂停/)
  await state.accept(sample({status:'submitted',revision:4}))
  await state.accept(sample({status:'active',revision:3}))
  assert.equal(state.attempt.value.status,'submitted')
  assert.equal(state.attempt.value.revision,4)
})

test('published zero and correction versions survive delayed older responses with the same exam revision', async () => {
  const {state}=await harness({initial:{status:'submitted',revision:4,grade:{score:0,version:1,comment:'已发布'}}})
  assert.equal(state.attempt.value.grade.score,0)
  await state.accept(sample({status:'submitted',revision:4,grade:{score:90,version:2,comment:'更正已发布'}}))
  await state.accept(sample({status:'submitted',revision:4,grade:{score:0,version:1}}))
  await state.accept(sample({status:'submitted',revision:4}))
  assert.equal(state.attempt.value.grade.score,90)
  assert.equal(state.attempt.value.grade.version,2)
})

test('closing an online page reports its durable exit with keepalive; repeat lifecycle events reuse the same ID', async () => {
  const {state,calls,storage}=await harness()
  state.beforeUnload();state.beforeUnload()
  const sends=calls.filter(c=>c.name==='keepalive')
  assert.equal(sends.length,2)
  assert.deepEqual(sends[0].args,sends[1].args)
  assert.equal(sends[0].args[1][0].kind,'exit')
  assert.deepEqual(JSON.parse(storage.get('srtp-exam-control-sid')).pending,sends[0].args[1])
  await state.accept(sample({status:'submitted',revision:3}))
  state.beforeUnload()
  assert.equal(calls.filter(c=>c.name==='keepalive').length,2)
})

test('exam route is outside campus navigation, with a dedicated exam console and no automatic scores or answers', async () => {
  const {source}=await harness()
  assert.ok(source.includes('exam-mode'))
  for(const field of ['standard_log','standard_session_id','ai_text','outcome.score','final_score']) assert.ok(!source.includes(field))
  const router=await readFile(new URL('../src/router/index.js',import.meta.url),'utf8')
  assert.match(router,/path: '\/student\/exams\/attempts\/:attemptId'.*requiresAuth: true, roles: \['student'\]/)
  const children=router.split('const children = [')[1].split('const router')[0]
  assert.ok(!children.includes('student/exams/attempts/:attemptId'))
})

test('refresh synchronizes the same attempt and recovers pending console clicks without reloading or leaving fullscreen',async()=>{
  const {state,calls}=await harness()
  const deadline=state.attempt.value.deadline, order=[]
  state.consoleRef.value={sync:()=>order.push('sync'),recover:async()=>order.push('recover')}
  await state.refreshExam()
  assert.deepEqual(order,['sync','recover']);assert.equal(state.attempt.value.deadline,deadline)
  assert.equal(state.attempt.value.session_id,'sid');assert.equal(state.refreshing.value,false)
  assert.ok(!calls.some(c=>['exitFullscreen','requestFullscreen','submit','keepalive'].includes(c.name)))
})
test('refresh does not discard an uncertain business click or pretend a recovery failure succeeded',async()=>{
  const {state}=await harness()
  state.consoleRef.value={sync:()=>{},recover:async()=>{throw new Error('操作尚未确认')}}
  await state.refreshExam()
  assert.match(state.notice.value,/尚未确认/);assert.equal(state.attempt.value.status,'active');assert.equal(state.refreshing.value,false)
})
