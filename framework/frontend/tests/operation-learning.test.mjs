import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { computed, ref } from 'vue'
import { parse } from '@vue/compiler-sfc'
import { attemptStatus, outcomeText, explanationStatus, learningError } from '../src/domain/operationLearning.js'
import { pageNumber } from '../src/domain/pagination.js'

const sample = values => ({session_id:'sid',question_id:1,status:'active',question:{title:'调车',number:1},console:{session_id:'sid',status:'active',events:[]},review:{revision:0,comment:null,confirmed:false},ai_status:'not_requested',...values})
async function harness(view = 'student/OperationAttempt', options = {}) {
  const source = await readFile(new URL(`../src/views/${view}.vue`, import.meta.url), 'utf8')
  const descriptor = parse(source).descriptor, calls = [], pending = [], guards = {}
  let current = sample(options.attempt)
  const route = {params:{attemptId:'sid'},query:{},...options.route}
  const invoke = (name, fn) => async (...args) => {calls.push({name,args:structuredClone(args)});return await fn(...args)}
  const deps = {
    computed, ref, attemptStatus, outcomeText, learningError, pageNumber,
    useRoute:() => route,useRouter:() => ({push:invoke('push',async()=>{}),replace:invoke('replace',async()=>{})}),
    onBeforeRouteLeave:fn => {guards.leave=fn},onBeforeRouteUpdate:fn => {guards.update=fn},watch:(getter,fn,config) => {if(config?.immediate)pending.push(fn())},
    onMounted:()=>{},onBeforeUnmount:()=>{},window:{addEventListener:()=>{},removeEventListener:()=>{}},
    ElMessageBox:{confirm:invoke('confirm',options.confirm || (async()=>{}))},
    getLearning:invoke('get',async()=>structuredClone(current)),
    submitLearning:invoke('submit',options.submit || (async()=>{current=sample({...current,status:'submitted',ai_status:'unconfigured',outcome:{status:'correct',score:100},console:{...current.console,status:'submitted'}});return structuredClone(current)})),
    explainLearning:invoke('explain',async()=>structuredClone(current)),
    downloadLearning:invoke('download',async()=>{}),
    beginLearning:invoke('begin',async()=>sample({session_id:'new'})),
    reviewLearning:invoke('review',options.review || (async(id,body)=>sample({...current,review:{...body,revision:body.revision+1}}))),
    learningConsoleApi:{},
  }
  const names = view.includes('Review') ? 'attempt,comment,confirmed,dirty,notice,saved,save,reload,explain,back' : 'attempt,consoleRef,notice,resultOpen,submit,restart,explain,back,working'
  const state = new Function(...Object.keys(deps),descriptor.scriptSetup.content.replace(/^import .*$/gm,'')+`\nreturn {${names}};`)(...Object.values(deps))
  await Promise.all(pending)
  return {state,calls,guards,route,source,template:descriptor.template.content}
}

test('submit waits for the real console flush and seals the UI with the server result',async()=>{
  const {state,calls} = await harness()
  let release
  const gate = new Promise(resolve=>{release=resolve})
  state.consoleRef.value={flush:()=>gate,sync:()=>{calls.push({name:'sync'})}}
  const submission=state.submit()
  assert.equal(state.working.value,true)
  assert.ok(!calls.some(call=>call.name==='submit'))
  release()
  await submission
  assert.deepEqual(calls.slice(-2).map(call=>call.name),['submit','sync'])
  assert.equal(state.attempt.value.status,'submitted')
  assert.equal(state.attempt.value.outcome.score,100)
  assert.equal(state.resultOpen.value,true)
  await state.submit()
  assert.equal(calls.filter(call=>call.name==='submit').length,1)
})

test('an unconfirmed click prevents submission, restart and navigation without losing input',async()=>{
  const {state,calls,guards}=await harness()
  state.consoleRef.value={flush:async()=>{throw new Error('点击尚未确认')}}
  await state.submit(); await state.restart()
  assert.ok(!calls.some(call=>['submit','begin'].includes(call.name)))
  assert.match(state.notice.value,/尚未确认/)
  assert.equal(await guards.leave(),false)
  assert.equal(state.attempt.value.status,'active')
})

test('restart cancellation sends no mutation; confirmed restart preserves the old record ID and return query',async()=>{
  const cancelled=await harness('student/OperationAttempt',{confirm:async()=>{throw 'cancel'}})
  await cancelled.state.restart()
  assert.ok(!cancelled.calls.some(call=>call.name==='begin'))
  const {state,calls}=await harness('student/OperationAttempt',{route:{query:{historyPage:'2'}}})
  await state.restart()
  assert.deepEqual(calls.find(call=>call.name==='begin').args,[1,'sid'])
  assert.deepEqual(calls.find(call=>call.name==='replace').args,[{path:'/student/learn/operations/attempts/new',query:{historyPage:'2'}}])
  assert.deepEqual(state.back.value,{path:'/student/learn/operations/history',query:{page:'2'}})
})

test('a review conflict preserves the unsaved comment and confirmation',async()=>{
  const {state,calls,guards}=await harness('teacher/OperationAttemptReview',{review:async()=>{throw {response:{data:{detail:'另一位教师已更新评阅，请刷新'}}}}})
  state.comment.value='保留的评语';state.confirmed.value=true
  await state.save()
  assert.equal(state.comment.value,'保留的评语');assert.equal(state.confirmed.value,true)
  assert.equal(state.dirty.value,true);assert.equal(state.saved.value,false)
  assert.match(state.notice.value,/另一位教师/)
  assert.deepEqual(calls.find(call=>call.name==='review').args,['sid',{revision:0,comment:'保留的评语',confirmed:true}])
  await guards.leave()
  assert.equal(calls.at(-1).name,'confirm')
})

test('result dock stays inside the campus content and exposes keyboard disclosure with reduced motion',async()=>{
  const {source,template}=await harness()
  assert.ok(source.includes('position:sticky'))
  assert.ok(template.includes('class="learning-work-area"'))
  assert.ok(!source.includes('position:fixed'))
  assert.ok(template.includes(':aria-expanded="resultOpen"'))
  assert.ok(template.includes('aria-controls="learning-results"'))
  assert.ok(source.includes('prefers-reduced-motion'))
  assert.ok(!source.includes('requestFullscreen'))
  const result=await readFile(new URL('../src/features/operationQuestions/LearningResult.vue',import.meta.url),'utf8')
  assert.ok(result.includes('ai分析日志')&&result.includes('ai评价讲解'))
  assert.ok(!result.includes('v-html'))
  assert.equal(outcomeText({status:'error',score:null}),'错误')
  assert.equal(explanationStatus('timeout'),'请求超时')
})
