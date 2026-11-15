import test from 'node:test'
import assert from 'node:assert/strict'
import {createQuestionTable,progressText} from '../src/features/chapterBank/useQuestionTable.js'
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return{promise,resolve,reject}}
test('ever-correct wording does not confuse an attempted mistake with an unanswered question',()=>{
  assert.equal(progressText({ever_correct:true,attempted:true}),'做对过')
  assert.equal(progressText({ever_correct:false,attempted:true}),'尚未做对')
  assert.equal(progressText({ever_correct:false,attempted:false}),'暂无答对记录')
})
test('filters reset pagination and a late old response cannot replace the chosen question list',async()=>{
  const first=deferred(),second=deferred(),calls=[]
  const table=createQuestionTable({get:(_,config)=>{calls.push(config.params);return calls.length===1?first.promise:second.promise}})
  table.page.value=3;const old=table.load()
  table.filters.progress='correct';table.filters.chapter=2;const fresh=table.apply()
  second.resolve({items:[{id:'correct'}],total:1});await fresh
  first.resolve({items:[{id:'outdated'}],total:366});await old
  assert.deepEqual(table.items.value,[{id:'correct'}]);assert.equal(table.total.value,1)
  assert.equal(calls[1].page,1);assert.equal(calls[1].progress,'correct');assert.equal(calls[1].chapter,2)
})
test('request failures provide retry and disposal prevents late data from appearing',async()=>{
  let fail=true
  const table=createQuestionTable({get:async()=>{if(fail)throw new Error();return{items:[],total:0}}})
  await table.load();assert.match(table.error.value,/加载失败/)
  fail=false;await table.load();assert.equal(table.error.value,'')
  const late=deferred();const other=createQuestionTable({get:()=>late.promise})
  const request=other.load();other.dispose();late.resolve({items:[{id:'late'}],total:1});await request
  assert.deepEqual(other.items.value,[])
})
