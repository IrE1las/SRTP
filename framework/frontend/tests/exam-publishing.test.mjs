import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { computed, reactive, ref, nextTick } from 'vue'
import { parse } from '@vue/compiler-sfc'
import { examPayload, beijingTime, beijingInput, examError, examStates, examFormErrors } from '../src/domain/exams.js'

const valid = () => ({name:'标准站考试',classes:['一班'],version_id:3,opens_at:'2030-01-02T12:00',closes_at:'2030-01-02T13:00',duration_minutes:30})
const record = (values={}) => ({id:7,revision:1,status:'draft',participant_count:0,attempt_count:0,...examPayload(valid()),...values})
async function harness(options={}) {
  const source=await readFile(new URL('../src/views/teacher/ExamEditor.vue',import.meta.url),'utf8')
  const script=parse(source).descriptor.scriptSetup.content.replace(/^import .*$/gm,'')
  const calls=[], pending=[], focused=[]
  const invoke=(name,fn)=>async(...args)=>{calls.push({name,args:structuredClone(args)});return fn(...args)}
  const route={params:options.existing?{examId:'7'}:{}}
  const deps={computed,reactive,ref,nextTick,examPayload,beijingTime,beijingInput,examError,examStates,examFormErrors,
    useRoute:()=>route,useRouter:()=>({replace:invoke('replace',async()=>{})}),useUserStore:()=>({role:'teacher'}),
    onMounted:()=>{},onBeforeUnmount:()=>{},onBeforeRouteLeave:()=>{},onBeforeRouteUpdate:()=>{},
    watch:(_,fn,config)=>{if(config?.immediate)pending.push(fn())},
    document:{getElementById:id=>({focus:()=>focused.push(id)})},
    ElMessageBox:{confirm:invoke('confirm',options.confirm||(async()=>{}))},
    getOperationClasses:async()=>({items:[{name:'一班',student_count:3}]}),getExam:async()=>record(),
    examVersions:async()=>({items:[{version_id:3,title:'调车',number:1}],total:1}),
    createExam:invoke('create',async body=>record(body)),
    editExam:invoke('edit',options.edit||(async(id,body)=>record({...body,revision:body.revision+1}))),
    publishExam:invoke('publish',options.publish||(async(id,revision)=>record({status:'published',revision:revision+1,participant_count:3}))),
    examParticipants:invoke('participants',async()=>({items:[],total:0})),examAttempts:invoke('attempts',async()=>({items:[],total:0})),
    withdrawExam:async()=>record(),copyExam:async()=>record(),window:{addEventListener:()=>{},removeEventListener:()=>{}},
  }
  const state=new Function(...Object.keys(deps),script+'\nreturn {form,errors,current,selectedTitle,working,notice,published,dirty,save,publish};')(...Object.values(deps))
  await Promise.all(pending)
  return {state,calls,focused}
}
test('complete new form publishes in one click without a preceding draft save action',async()=>{
  const {state,calls}=await harness()
  Object.assign(state.form,valid());state.selectedTitle.value='调车 · v1'
  await state.publish()
  assert.deepEqual(calls.map(c=>c.name),['confirm','create','publish','participants','attempts','replace'])
  assert.equal(state.published.value,true)
  assert.deepEqual(calls.find(c=>c.name==='publish').args,[7,1])
  assert.equal(state.working.value,false)
})
test('missing fields are identified beside inputs and focus the first error without saving or publishing',async()=>{
  const {state,calls,focused}=await harness()
  await state.publish()
  assert.deepEqual(Object.keys(state.errors.value),['name','classes','opens_at','closes_at','duration_minutes','version_id'])
  assert.equal(focused[0],'exam-name');assert.equal(calls.length,0)
  Object.assign(state.form,valid(),{closes_at:''})
  await state.publish()
  assert.deepEqual(Object.keys(state.errors.value),['closes_at']);assert.equal(focused.at(-1),'exam-closes-at')
})
test('editing a saved draft automatically persists its latest fields before publication',async()=>{
  const {state,calls}=await harness({existing:true})
  state.form.name='更新后的考试'
  await state.publish()
  assert.equal(calls.find(c=>c.name==='edit').args[1].name,'更新后的考试')
  assert.deepEqual(calls.find(c=>c.name==='publish').args,[7,2])
})
test('optional incomplete draft saving remains available; publish cancellation keeps inputs and sends no mutations',async()=>{
  const draft=await harness();draft.state.form.name='未完成';await draft.state.save()
  assert.deepEqual(draft.calls.map(c=>c.name),['create','replace'])
  const cancel=await harness({confirm:async()=>{throw new Error('cancel')}})
  Object.assign(cancel.state.form,valid());await cancel.state.publish()
  assert.deepEqual(cancel.calls.map(c=>c.name),['confirm']);assert.equal(cancel.state.form.name,'标准站考试');assert.equal(cancel.state.working.value,false)
})
test('failed publication preserves the returned draft so retry does not create a second exam',async()=>{
  let attempts=0
  const {state,calls}=await harness({publish:async(id,revision)=>{if(!attempts++)throw new Error('network');return record({status:'published',revision:revision+1})}})
  Object.assign(state.form,valid());await state.publish()
  assert.equal(state.published.value,false);assert.equal(state.current.value.id,7)
  await state.publish()
  assert.equal(calls.filter(c=>c.name==='create').length,1);assert.equal(state.published.value,true)
})
test('an edit revision conflict preserves input and blocks publication',async()=>{
  const {state,calls}=await harness({existing:true,edit:async()=>{throw {response:{data:{detail:'考试配置已变化'}}}}})
  state.form.name='保留修改';await state.publish()
  assert.equal(state.form.name,'保留修改');assert.equal(state.dirty.value,true)
  assert.ok(!calls.some(c=>c.name==='publish'));assert.match(state.notice.value,/已变化/)
})
