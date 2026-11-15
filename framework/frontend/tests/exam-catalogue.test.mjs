import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { ref } from 'vue'
import { parse } from '@vue/compiler-sfc'
import { beijingTime, examStates, examError, enterExam, examAction } from '../src/domain/exams.js'

test('unified student catalogue keeps all states and only open/active actions can request fullscreen or begin',async()=>{
  const source=await readFile(new URL('../src/views/student/Exams.vue',import.meta.url),'utf8')
  const rows=['active','open','upcoming','missed','submitted'].map((state,i)=>({id:i+1,state}))
  const calls=[], document={fullscreenElement:null,documentElement:{requestFullscreen:async()=>{calls.push('fullscreen');document.fullscreenElement={}}},exitFullscreen:async()=>{}}
  const deps={ref,beijingTime,examStates,examError,enterExam,examAction,document,
    useRoute:()=>({query:{}}),useRouter:()=>({push:async path=>calls.push(path),replace:async()=>{}}),
    onMounted:()=>{},onBeforeUnmount:()=>{},setInterval:()=>1,clearInterval:()=>{},
    listExams:async()=>({items:rows,total:5}),beginExam:async id=>{calls.push('begin-'+id);return {session_id:'sid'}},
  }
  const script=parse(source).descriptor.scriptSetup.content.replace(/^import .*$/gm,'')
  const state=new Function(...Object.keys(deps),script+'\nreturn {items,total,load,participate};')(...Object.values(deps))
  await state.load();assert.equal(state.items.value.length,5);assert.equal(state.total.value,5)
  for(const row of rows.slice(2))await state.participate(row)
  assert.equal(calls.length,0)
  assert.deepEqual(rows.map(examAction),['恢复考试','全屏参加考试','未开始','已结束','已结束'])
  await state.participate(rows[1])
  assert.deepEqual(calls,['fullscreen','begin-2','/student/exams/attempts/sid'])
})
