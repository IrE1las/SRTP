import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { computed,nextTick,reactive,ref,watch } from 'vue'
import { createRouter,createMemoryHistory } from 'vue-router'
import { parse } from '@vue/compiler-sfc'
import { THEORY_ROOT,theoryTopicPath,theoryPlatform,theoryPlatformName,theoryHistoryPath } from '../src/domain/theoryNavigation.js'
import { paginate,pageNumber,LIST_PAGE_SIZE } from '../src/domain/pagination.js'
import { COMMANDS } from '../src/features/simulationConsole/standardDisplay.js'

const catalog=Array.from({length:18},(_,index)=>{
  const topic=Math.floor(index/3)+1
  return {id:index+1,key:'lab-'+String(topic).padStart(2,'0')+'-'+String(index%3+1).padStart(2,'0'),topic,
    topic_info:{id:topic,title:'专题'+topic},fingerprint:'a'.repeat(64),fields:[{id:'answer',kind:'choice',options:['是','否']}]}
})
async function component(path) {
  const source=await readFile(new URL('../src/'+path,import.meta.url),'utf8')
  return {source,...parse(source).descriptor}
}
async function harness(path,{params={},query={},mocks={},expose=[]}={}) {
  const descriptor=await component(path)
  const script=descriptor.scriptSetup.content.replace(/^import .*$/gm,'')
  const route=reactive({path:'/student/learn/theory'+(params.topicId?'/'+params.topicId:''),params,query})
  const calls=[],storage=new Map()
  let mounted
  const router={
    replace:async value=>{calls.push(['replace',value]);route.path=value.path;route.query=value.query||{}},
    push:value=>{calls.push(['push',value])},
  }
  const deps={computed,nextTick,reactive,ref,watch,onMounted:fn=>{mounted=fn},useRoute:()=>route,useRouter:()=>router,
    useUserStore:()=>({role:'student',user:{id:7}}),
    THEORY_ROOT,theoryTopicPath,theoryPlatform,theoryPlatformName,theoryHistoryPath,
    TheoryStationCanvas:{},TheorySimulationConsole:{},Notation:{},ListPager:{},paginate,pageNumber,LIST_PAGE_SIZE,topology:{signals:[],switches:[],sections:[]},
    getLabQuestions:async()=>{calls.push(['catalog']);return catalog},
    getLabQuestion:async key=>{calls.push(['question',key]);return catalog.find(q=>q.key===key)},
    getLabAttemptPage:async(topic,page)=>{calls.push(['history-page',topic,page]);return {items:[{id:topic,topic}],page,total:(page-1)*6+1,page_size:6,page_count:page}},
    getLabAttempt:async id=>{calls.push(['own-detail',id]);return {id:Number(id),topic:5,answers:{answer:'是'},result:{feedback:[]}}},
    getLabAttempts:async topic=>{calls.push(['history',topic]);return [{id:topic,topic}]},
    getReviewStudents:async topic=>{calls.push(['roster',topic]);return [{id:7,username:'student',attempt_count:1,pending_count:1}]},
    getReviewStudentAttempts:async id=>{calls.push(['student-list',id]);return {student:{id},attempts:[{id:22,topic:1,status:'pending_review'}]}},
    getReviewAttempt:async id=>{calls.push(['detail',id]);return {id:Number(id),student:{id:7},rubric:[{id:'reason',points:10}],review:null,result:{status:'pending_review'}}},
    reviewLabAttempt:async(id,data)=>{calls.push(['grade',id,data]);return {review:data,result:{status:'graded',total_score:48}}},
    submitLabAnswer:async(key,body)=>{calls.push(['submit',key,body]);return {id:99,topic:catalog.find(q=>q.key===key).topic,answers:body.answers,result:{status:'pending_review'}}},
    localStorage:{getItem:key=>storage.get(key)??null,setItem:(key,value)=>storage.set(key,value)},
    ...mocks,
  }
  const state=new Function(...Object.keys(deps),script+'\nreturn {'+expose.join(',')+'};')(...Object.values(deps))
  await mounted()
  await nextTick()
  return {state,calls,route,router,descriptor}
}

test('theory catalogue contains links only; no question, original-image modal or answers below entries',async()=>{
  const {state,calls,descriptor}=await harness('views/student/LabTopics.vue',{expose:['questions','topics','notice']})
  assert.equal(state.topics.value.length,6)
  assert.deepEqual(calls,[['catalog']])
  assert.ok(descriptor.template.content.includes(':to="theoryTopicPath(topic.id)"'))
  for(const unwanted of ['answer-form','TheoryStationCanvas','TheorySimulationConsole','查看原始站场','实验报告对应位置','showOriginal']) {
    assert.ok(!descriptor.template.content.includes(unwanted),unwanted)
  }
})
test('old bookmarked question query opens its dedicated topic route',async()=>{
  const {calls}=await harness('views/student/LabTopics.vue',{query:{q:'lab-02-01'}})
  assert.deepEqual(calls.at(-1),['replace',{path:'/student/learn/theory/2',query:{q:'lab-02-01'}}])
})
test('all six question pages load and submit independently, with platforms 1-4 and 5-6 separated',async()=>{
  for(let topic=1;topic<=6;topic++) {
    const {state,calls,descriptor}=await harness('views/student/TheoryTopic.vue',{
      params:{topicId:String(topic)},expose:['question','answers','result','notice','chooseQuestion','submit','topicQuestions']})
    assert.equal(state.notice.value,'')
    assert.equal(state.question.value.topic,topic)
    assert.equal(state.topicQuestions.value.length,3)
    assert.equal(theoryPlatform(topic),topic<=4?'simulation-console':'interlocking-table')
    assert.ok(!descriptor.template.content.includes('topic-grid'))
    assert.ok(!descriptor.template.content.includes('实验报告对应位置'))
    state.answers.value.answer='是'
    await state.submit()
    assert.equal(state.result.value.result.status,'pending_review')
    assert.ok(calls.some(row=>row[0]==='submit'&&row[1]===state.question.value.key))
    await state.chooseQuestion('lab-'+String(topic).padStart(2,'0')+'-03')
    assert.ok(state.question.value.key.endsWith('-03'))
  }
})
test('my answers replaces the catalogue and requests only the selected topic',async()=>{
  const {state,calls,descriptor}=await harness('views/student/TheoryHistory.vue',{query:{topic:'5'},expose:['attempts','topicId']})
  assert.equal(state.topicId.value,5)
  assert.deepEqual(state.attempts.value,[{id:5,topic:5}])
  assert.deepEqual(calls.at(-1),['history-page',5,1])
  assert.ok(!descriptor.template.content.includes('topic-grid'))
})
test('teacher first sees only roster data, then only one student list, then a single selected answer',async()=>{
  const roster=await harness('views/teacher/TheoryStudentList.vue',{expose:['openStudent','students']})
  assert.deepEqual(roster.calls,[['catalog'],['roster',undefined]])
  assert.ok(!roster.descriptor.template.content.includes('学生作答</strong>'))
  assert.ok(!roster.descriptor.template.content.includes('内容预览'))
  roster.state.openStudent(7)
  assert.deepEqual(roster.calls.at(-1),['push',{path:'/teacher/questions/students/7',query:{studentsPage:'1'}}])
  const list=await harness('views/teacher/TheoryStudentAttempts.vue',{params:{studentId:'7'},expose:['attempts']})
  assert.deepEqual(list.calls,[['student-list','7']])
  assert.ok(!list.descriptor.template.content.includes('attempt.answers'))
  const detail=await harness('views/teacher/TheoryReview.vue',{params:{attemptId:'22'},expose:['attempt','scores','comment','save']})
  assert.deepEqual(detail.calls,[['detail','22']])
  detail.state.scores.value.reason=8
  detail.state.comment.value='核对完成'
  await detail.state.save()
  assert.deepEqual(detail.calls.at(-1),['grade',22,{scores:{reason:8},comment:'核对完成'}])
  assert.equal(detail.state.attempt.value.result.total_score,48)
})
test('late detail response cannot replace a different student answer',async()=>{
  let release,blockFirst=false
  const {state,route}=await harness('views/teacher/TheoryReview.vue',{
    params:{attemptId:'1'},expose:['attempt','load'],
    mocks:{getReviewAttempt:id=>id==='1'&&blockFirst?new Promise(resolve=>{release=resolve}):Promise.resolve({id:Number(id),student:{id:7},rubric:[],review:null})},
  })
  blockFirst=true
  const old=state.load()
  route.params.attemptId='2'
  await state.load()
  await nextTick()
  release({id:1,student:{id:7},rubric:[],review:null})
  await old
  assert.equal(state.attempt.value.id,2)
})
test('required topic and roster API parameters are forwarded',async()=>{
  const source=(await readFile(new URL('../src/api/labTopics.js',import.meta.url),'utf8'))
    .replace(/^import request.*$/m,'const request={get:(...args)=>args}')
  const api=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'))
  assert.deepEqual(api.getLabAttempts(3),['/lab-topics/attempts',{params:{topic:3}}])
  assert.deepEqual(api.getReviewStudents(6),['/lab-topics/review-students',{params:{topic:6}}])
  assert.deepEqual(api.getReviewStudentAttempts(7,2),['/lab-topics/review-students/7/attempts',{params:{topic:2}}])
})
test('console client is anchored to the exact question and cannot select the other station',async()=>{
  const source=(await readFile(new URL('../src/api/theoryConsole.js',import.meta.url),'utf8'))
    .replace(/^import request.*$/m,'const request={get:(...args)=>args,post:(...args)=>args}')
  const {createTheoryConsoleClient}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'))
  const client=createTheoryConsoleClient('lab-01-01')
  assert.deepEqual(client.getStationPackage(),['/lab-topics/questions/lab-01-01/console/station'])
  assert.deepEqual(client.createSimulationSession(false),['/lab-topics/questions/lab-01-01/console/sessions',{interval_available:false,occupied_sections:[]}])
  assert.deepEqual(client.pressStationButton('session','D3DA',4),['/lab-topics/questions/lab-01-01/console/sessions/session/buttons',{button:'D3DA',version:4}])
  assert.throws(()=>createTheoryConsoleClient('lab-05-01'))
  assert.throws(()=>createTheoryConsoleClient('lab-07-01'))
})
test('photographed console setup and real function selection invoke the bound operational API without a browser',async()=>{
  const {scriptSetup,template}=await component('features/simulationConsole/TheorySimulationConsole.vue')
  const script=scriptSetup.content.replace(/^import .*$/gm,'')
  assert.ok(!template.content.includes('source-picker'))
  assert.ok(!template.content.includes('<StationDiagram'))
  let mounted,unmount
  const calls=[],storage=new Map()
  let snap={session_id:'q1-console',version:0,routes:[],selected_buttons:[],sections:{},switches:{}}
  const client={
    getStationPackage:async()=>({station_name:'标准站',counts:{candidate_routes:199},buttons:[],routes:[]}),
    createSimulationSession:async()=>snap,
    getSimulationSnapshot:async()=>snap,
    getSimulationReplay:async()=>[snap],
    pressStationButton:async(id,button,version)=>{calls.push(['button',id,button,version]);snap={...snap,version:version+1};return {accepted:true,snapshot:snap}},
    operateConsole:async(id,command,version)=>{calls.push(['command',id,command.type,command.target,version]);snap={...snap,version:version+1};return {accepted:true,snapshot:snap}},
    clearStationSelection:async()=>({accepted:true,snapshot:snap}),advanceSimulationTrain:async()=>({accepted:true,snapshot:snap}),
  }
  const deps={computed,nextTick,ref,onMounted:fn=>{mounted=fn},onBeforeUnmount:fn=>{unmount=fn},
    defineProps:()=>({questionKey:'lab-01-01'}),useUserStore:()=>({role:'student',user:{id:7}}),
    createTheoryConsoleClient:key=>{assert.equal(key,'lab-01-01');return client},COMMANDS,
    ReferenceStationDiagram:{},ElMessage:{info:()=>{},warning:()=>{}},
    sessionStorage:{getItem:key=>storage.get(key)??null,setItem:(key,value)=>storage.set(key,value),removeItem:key=>storage.delete(key)},
    document:{addEventListener:()=>{},removeEventListener:()=>{},fullscreenElement:null},
    window:{setInterval:()=>1},clearInterval:()=>{},
  }
  const state=new Function(...Object.keys(deps),script+'\nreturn {chooseCommand,selectGroup,pressButton,loading,stale,canControlTrain};')(...Object.values(deps))
  await mounted()
  assert.equal(state.loading.value,false)
  assert.equal(state.stale.value,false)
  assert.equal(state.canControlTrain.value,true)
  await state.chooseCommand({type:'SWITCH_SINGLE_LOCK',target:'switch',label:'单锁'})
  await state.selectGroup('5')
  assert.deepEqual(calls.at(-1),['command','q1-console','SWITCH_SINGLE_LOCK','5',0])
  await state.pressButton('D3DA')
  assert.deepEqual(calls.at(-1),['button','q1-console','D3DA',1])
  unmount()
})
test('router separates catalogue/topic/history and restricts teacher pages; admin management routes are absent',async()=>{
  let source=await readFile(new URL('../src/router/index.js',import.meta.url),'utf8')
  source=source.replace(/^import .*$/gm,'').replace(/^export \{ roleHomeMap \}$/m,'')
    .replace(/\(\) => import\([^)]*\)/g,'() => Promise.resolve({render:()=>null})').replace('export default router','return router')
  const homes={student:'/student/dashboard',teacher:'/teacher/dashboard',admin:'/admin'}
  for(const role of ['student','teacher','admin']) {
    const user={role,isLoggedIn:true}
    const router=new Function('createRouter','createWebHistory','AppLayout','useUserStore','roleHomeMap',source)(createRouter,createMemoryHistory,{},()=>user,homes)
    await router.push('/')
    assert.equal(router.currentRoute.value.path,homes[role])
    const catalogue=router.resolve('/student/learn/theory').matched.at(-1).path
    const question=router.resolve('/student/learn/theory/1').matched.at(-1).path
    const history=router.resolve('/student/learn/theory/attempts').matched.at(-1).path
    assert.notEqual(catalogue,question)
    assert.notEqual(question,history)
    assert.notEqual(history,catalogue)
    if(role!=='teacher') {
      await router.push('/teacher/questions/students/7')
      assert.equal(router.currentRoute.value.path,homes[role])
    }
    for(const path of ['/admin/questions','/admin/exams','/admin/questions/theory','/student/simulation-console','/student/modules','/teacher/questions/theory']) {
      assert.equal(router.resolve(path).matched.at(-1).path,'/:pathMatch(.*)*')
    }
    user.isLoggedIn=false
    await router.push('/student/learn/theory/1')
    assert.equal(router.currentRoute.value.path,'/login')
  }
})
test('study and exam menus begin collapsed and toggle independently',async()=>{
  const {scriptSetup}=await component('layout/SidebarMenu.vue')
  const source=scriptSetup.content.replace(/^import .*$/gm,'')
  const state=new Function('computed','ref','useRoute','useUserStore','navigationForRole','defineEmits',source+'\nreturn {expanded,toggle};')(computed,ref,()=>({path:'/student/dashboard'}),()=>({role:'student'}),()=>[],()=>{})
  assert.deepEqual(state.expanded.value,{})
  state.toggle('/student/learn');state.toggle('/student/exams');state.toggle('/student/learn')
  assert.equal(state.expanded.value['/student/learn'],false)
  assert.equal(state.expanded.value['/student/exams'],true)
})


test('answer list links to a separate own-detail page and returning preserves topic and page',async()=>{
  const list=await harness('views/student/TheoryHistory.vue',{
    query:{topic:'5',page:'2'},expose:['detailPath','page'],
  })
  assert.ok(!list.descriptor.template.content.includes('<details'))
  assert.ok(!list.descriptor.template.content.includes('attempt.answers'))
  assert.equal(list.state.page.value,2)
  const link=list.state.detailPath(42)
  assert.deepEqual(link,{path:THEORY_ROOT+'/attempts/42',query:{topic:'5',page:'2'}})
  assert.ok(!list.calls.some(row=>row[0]==='own-detail'))
  const detail=await harness('views/student/TheoryAttemptDetail.vue',{
    params:{attemptId:'42'},query:link.query,expose:['attempt','backPath'],
  })
  assert.deepEqual(detail.calls,[['own-detail','42']])
  assert.deepEqual(detail.state.backPath.value,{path:THEORY_ROOT+'/attempts',query:{topic:'5',page:'2'}})
  assert.equal(detail.state.attempt.value.id,42)
})
test('all list pagination has six items, stable boundaries, truthful empty state and clamps after a list shrinks',()=>{
  const items=Array.from({length:13},(_,i)=>i+1)
  assert.deepEqual(paginate(items,1).items,[1,2,3,4,5,6])
  assert.deepEqual(paginate(items,2).items,[7,8,9,10,11,12])
  assert.deepEqual(paginate(items,3).items,[13])
  assert.equal(paginate(items,99).page,3)
  assert.deepEqual(paginate([],10),{page:1,pageCount:1,total:0,pageSize:6,items:[]})
  assert.deepEqual(paginate([1,2],3).items,[1,2])
  for(const value of [0,-1,'invalid',1.5,Infinity])assert.equal(pageNumber(value),1)
})
test('current six-topic catalogue uses the shared pager and keeps the six-topic rule',async()=>{
  const result=await harness('views/student/LabTopics.vue',{expose:['pageView']})
  assert.equal(result.state.pageView.value.items.length,6)
  assert.equal(result.state.pageView.value.pageCount,1)
  assert.ok(result.descriptor.template.content.includes('ListPager'))
})
test('a longer question list is paged by six and changing page selects a question on that page',async()=>{
  const rows=Array.from({length:13},(_,i)=>({...catalog[0],id:i+1,key:'lab-01-'+String(i+1).padStart(2,'0')}))
  const result=await harness('views/student/TheoryTopic.vue',{
    params:{topicId:'1'},mocks:{getLabQuestions:async()=>rows,getLabQuestion:async key=>rows.find(q=>q.key===key)},
    expose:['questionPageView','changeQuestionPage','question'],
  })
  assert.equal(result.state.questionPageView.value.items.length,6)
  await result.state.changeQuestionPage(2)
  assert.deepEqual(result.state.questionPageView.value.items.map(q=>q.id),[7,8,9,10,11,12])
  assert.equal(result.state.question.value.key,'lab-01-07')
  await result.state.changeQuestionPage(3)
  assert.equal(result.state.questionPageView.value.items.length,1)
})
test('teacher lists show six rows and keep roster and attempt page positions separate',async()=>{
  const roster=await harness('views/teacher/TheoryStudentList.vue',{
    query:{page:'2'},mocks:{getReviewStudents:async()=>Array.from({length:13},(_,i)=>({id:i+1,username:'student'+(i+1),student_number:'2026'+String(i+1).padStart(3,'0'),attempt_count:1}))},
    expose:['pageView','openStudent','search'],
  })
  assert.deepEqual(roster.state.pageView.value.items.map(row=>row.id),[7,8,9,10,11,12])
  roster.state.openStudent(8)
  assert.deepEqual(roster.calls.at(-1),['push',{path:'/teacher/questions/students/8',query:{studentsPage:'2'}}])
  roster.state.search.value='2026013'
  await nextTick()
  assert.equal(roster.state.pageView.value.page,1)
  assert.equal(roster.state.pageView.value.total,1)
  const attempts=await harness('views/teacher/TheoryStudentAttempts.vue',{
    params:{studentId:'8'},query:{page:'3',studentsPage:'2'},
    mocks:{getReviewStudentAttempts:async()=>({student:{id:8},attempts:Array.from({length:13},(_,i)=>({id:i+1}))})},
    expose:['pageView','backPath'],
  })
  assert.deepEqual(attempts.state.pageView.value.items.map(row=>row.id),[13])
  assert.equal(attempts.state.backPath.value.query.page,'2')
})
test('administrator user list also limits each page to six existing accounts',async()=>{
  const result=await harness('views/admin/UserManagement.vue',{
    mocks:{listAdminUsers:async()=>Array.from({length:13},(_,i)=>({id:i+1}))},expose:['pageView','page'],
  })
  assert.equal(result.state.pageView.value.items.length,6)
  result.state.page.value=3
  assert.deepEqual(result.state.pageView.value.items.map(row=>row.id),[13])
})

test('user role filter applies before six-item pagination, restores from the URL and resets the page',async()=>{
  const rows=Array.from({length:18},(_,i)=>({id:i+1,role:i<13?'student':i<17?'teacher':'admin'}))
  const result=await harness('views/admin/UserManagement.vue',{
    query:{role:'student'},mocks:{listAdminUsers:async()=>rows},expose:['pageView','page','selectedRole','changeRole','replaceUser'],
  })
  assert.equal(result.state.pageView.value.total,13)
  result.state.page.value=3
  assert.deepEqual(result.state.pageView.value.items.map(row=>row.id),[13])
  await result.state.changeRole('teacher')
  assert.equal(result.state.page.value,1)
  assert.equal(result.state.pageView.value.total,4)
  assert.ok(result.state.pageView.value.items.every(row=>row.role==='teacher'))
  result.state.replaceUser({id:14,role:'student'})
  assert.equal(result.state.pageView.value.total,3)
  await result.state.changeRole('admin')
  assert.deepEqual(result.state.pageView.value.items.map(row=>row.id),[18])
  await result.state.changeRole('all')
  assert.equal(result.state.pageView.value.total,18)
})
test('the former return-to-six-topics label is simply Return',async()=>{
  for(const path of ['views/student/TheoryTopic.vue','views/student/TheoryHistory.vue']) {
    const {template}=await component(path)
    assert.ok(!template.content.includes('返回六专题'))
    assert.ok(template.content.includes('>返回</router-link>'))
  }
})

test('teacher roster independently filters class and student number, sorts naturally and carries filters into the return link',async()=>{
  const rows=[{id:2,student_name:'同名',student_number:'10',class_name:'二班',attempt_count:1},{id:3,student_name:'同名',student_number:'2',class_name:'二班',attempt_count:1},{id:1,student_name:'10',student_number:'11',class_name:'一班',attempt_count:1}]
  const roster=await harness('views/teacher/TheoryStudentList.vue',{mocks:{getReviewStudents:async()=>rows},expose:['pageView','classes','className','search','openStudent','applyFilters']})
  assert.deepEqual(roster.state.classes.value.sort(),['一班','二班'].sort())
  roster.state.className.value='二班'
  assert.deepEqual(roster.state.pageView.value.items.map(row=>row.student_number),['2','10'])
  roster.state.search.value='10'
  assert.deepEqual(roster.state.pageView.value.items.map(row=>row.id),[2])
  roster.state.openStudent(2)
  assert.deepEqual(roster.calls.at(-1),['push',{path:'/teacher/questions/students/2',query:{class:'二班',search:'10',studentsPage:'1'}}])
  const attempts=await harness('views/teacher/TheoryStudentAttempts.vue',{params:{studentId:'2'},query:{class:'二班',search:'10',studentsPage:'2'},expose:['backPath']})
  assert.deepEqual(attempts.state.backPath.value,{path:'/teacher/questions',query:{class:'二班',search:'10',page:'2'}})
})
