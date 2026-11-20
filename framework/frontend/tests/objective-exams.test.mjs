import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { computed, ref } from 'vue'
import { parse } from '@vue/compiler-sfc'
import { answered, emptyAnswer, answerText } from '../src/domain/objectiveExams.js'
import { examPayload, examFormErrors, examError } from '../src/domain/exams.js'

const sample = () => ({session_id:'objective-session',status:'active',answer_revision:0,answers:{},question:{items:[{id:'one',kind:'true_false',points:50},{id:'two',kind:'cell',blank_count:2,points:50}]}})
async function harness(options={}) {
  const source=await readFile(new URL('../src/features/exams/ObjectiveExamAnswers.vue',import.meta.url),'utf8')
  const script=parse(source).descriptor.scriptSetup.content.replace(/^import .*$/gm,'')
  const props={attempt:sample(),disabled:false}, calls=[], observers=[], storage=new Map(options.local ? [['srtp-exam-answers-objective-session',JSON.stringify(options.local)]] : [])
  const deps={computed,ref,answered,examError,watch:(_,callback)=>observers.push(callback),defineProps:()=>props,defineEmits:()=> (event,value)=>{calls.push({event,value})},defineExpose:()=>{},onBeforeUnmount:()=>{},
    localStorage:{getItem:key=>storage.get(key) || null,setItem:(key,value)=>storage.set(key,value)},
    getExamAttempt:async()=>options.server || sample(),
    saveObjectiveAnswers:async(id,body)=>{calls.push({id,body:structuredClone(body)});return options.save ? options.save(id,body) : {...sample(),answer_revision:body.revision+1,answers:body.answers}},
    setTimeout:()=>1,clearTimeout:()=>{},document:{getElementById:()=>null},ElMessageBox:{confirm:options.confirm || (async()=>{})}}
  const state=new Function(...Object.keys(deps),script+'\nreturn {answers,revision,dirty,completed,saving,error,edit,flush,refresh};')(...Object.values(deps))
  return {props,state,calls,storage,observers}
}

test('objective paper keeps type, order and points, ignores the operation version and validates total',()=>{
  const form={kind:'objective',name:'试卷',classes:['一班'],version_id:9,opens_at:'2030-01-01T12:00',closes_at:'2030-01-01T13:00',duration_minutes:30,objective_questions:[{question_id:'two',points:40},{question_id:'one',points:60}]}
  assert.equal(examPayload(form).version_id,null)
  assert.deepEqual(examPayload(form).objective_questions,form.objective_questions)
  assert.deepEqual(examFormErrors(form,0),{})
  form.objective_questions[0].points=39
  assert.deepEqual(Object.keys(examFormErrors(form,0)),['paper'])
  assert.ok(!examFormErrors(form,0).version_id)
})
test('false is a completed judgement, empty multi and partial fill remain unanswered',()=>{
  assert.equal(answered({kind:'true_false'},false),true)
  assert.equal(answered({kind:'multi'},[]),false)
  assert.equal(answered({kind:'cell',blank_count:2},['甲',' ']),false)
  assert.equal(answered({kind:'cell',blank_count:2},['甲','乙']),true)
  assert.deepEqual(emptyAnswer({kind:'cell',blank_count:2}),['',''])
  assert.equal(answerText(false),'错误')
})
test('actual answer component preserves false and partial fill and saves their exact revision',async()=>{
  const {state,calls,storage}=await harness()
  state.edit('one',false);state.edit('two',['甲',''])
  assert.equal(state.completed.value,1)
  assert.equal(state.dirty.value,true)
  assert.equal(await state.flush(),1)
  assert.equal(state.dirty.value,false)
  assert.deepEqual(calls.find(call=>call.body).body,{revision:0,answers:{one:false,two:['甲','']}})
  assert.equal(JSON.parse(storage.get('srtp-exam-answers-objective-session')).revision,1)
})
test('edits made during a save are sent in order before the submission flush completes',async()=>{
  let release, count=0
  const gate=new Promise(resolve=>{release=resolve})
  const {state,calls}=await harness({save:async(id,body)=>{if(count++===0)await gate;return {...sample(),answer_revision:body.revision+1}}})
  state.edit('one',false)
  const first=state.flush()
  state.edit('two',['甲','乙'])
  const second=state.flush()
  release()
  assert.deepEqual(await Promise.all([first,second]),[2,2])
  assert.deepEqual(calls.filter(call=>call.body).map(call=>call.body.revision),[0,1])
  assert.equal(state.dirty.value,false)
})
test('lost save response keeps the original revision and draft for idempotent retry',async()=>{
  let count=0
  const {state,calls}=await harness({save:async()=>{if(count++===0)throw new Error('lost');return {...sample(),answer_revision:1}}})
  state.edit('one',false)
  await assert.rejects(state.flush())
  assert.equal(state.dirty.value,true);assert.equal(state.revision.value,0)
  assert.equal(await state.flush(),1)
  assert.deepEqual(calls.filter(call=>call.body).map(call=>call.body.revision),[0,0])
})
test('server conflicts retain local answers and require explicit acceptance before reloading',async()=>{
  const {state}=await harness({save:async()=>{throw {response:{data:{detail:'答案已在其他页面修改'}}}},confirm:async()=>{throw new Error('cancel')}})
  state.edit('one',false)
  await assert.rejects(state.flush())
  assert.match(state.error.value,/其他页面/)
  await state.refresh()
  assert.equal(state.answers.value.one,false);assert.equal(state.dirty.value,true)
})
test('restoring an unacknowledged local draft retains its original server revision',async()=>{
  const {state}=await harness({local:{revision:0,answers:{one:false}}})
  assert.equal(state.answers.value.one,false);assert.equal(state.dirty.value,true)
  assert.equal(await state.flush(),1)
})
test('resuming after an offline or fullscreen pause automatically saves the pending draft',async()=>{
  const {props,state,calls,observers}=await harness()
  state.edit('one',false)
  props.disabled=true
  observers[0](true)
  assert.equal(calls.filter(call=>call.body).length,0)
  props.disabled=false
  observers[0](false)
  await state.flush()
  assert.equal(state.dirty.value,false)
  assert.equal(calls.filter(call=>call.body).length,1)
})
