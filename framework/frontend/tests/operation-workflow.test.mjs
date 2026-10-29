import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { computed, reactive, ref } from 'vue'
import { parse } from '@vue/compiler-sfc'
import { COMMANDS } from '../src/features/simulationConsole/standardDisplay.js'
import { eventEnvelope, persistableEvent, initialForm, draftPayload } from '../src/domain/operationEvents.js'
import { paginate } from '../src/domain/pagination.js'

async function consoleHarness({ stored, failOnce = false, initialPending = null } = {}) {
  const source = await readFile(new URL('../src/features/simulationConsole/OperationConsole.vue', import.meta.url), 'utf8')
  const descriptor = parse(source).descriptor
  const calls = [], updates = [], storage = new Map(stored ? [['srtp-operation-pending-sid', JSON.stringify(stored)]] : [])
  let mount, unmount, exposed, failed = false
  const server = { session_id:'sid', revision:0, status:'active', pending:initialPending, events:[], snapshot:{ session_kind:'recording', selected_buttons:[], switches:{} } }
  const dependencies = {
    computed, ref, COMMANDS, eventEnvelope, persistableEvent,
    defineProps: () => ({ sessionId:'sid' }), defineEmits: () => (_, data) => updates.push(data), defineExpose: value => { exposed = value },
    onMounted: fn => { mount = fn }, onBeforeUnmount: fn => { unmount = fn },
    setInterval: () => 1, clearInterval: () => {},
    sessionStorage: { setItem:(key,value) => storage.set(key,value), getItem:key => storage.get(key), removeItem:key => storage.delete(key) },
    getOperationStation: async () => ({ buttons:[{ name:'D3DA', signal:'D3' }] }),
    getOperationSession: async () => structuredClone(server),
    postOperationEvent: async (sid, event) => {
      calls.push(structuredClone(event))
      if (failOnce && !failed) { failed = true; throw new Error('network uncertain') }
      if (!server.events.some(row => row.event_id === event.event_id)) {
        assert.equal(event.sequence, server.revision + 1)
        server.events.push(event); server.revision++
        server.pending = event.action === 'function' && event.button_id !== 'CLEAR_SELECTION' ? { type:event.button_id, target:'signal' } : null
      }
      return structuredClone(server)
    },
  }
  const script = descriptor.scriptSetup.content.replace(/^import .*$/gm, '')
  const state = new Function(...Object.keys(dependencies), script + '\nreturn {choose, target, press, group, signal, inspect, block, confirmPin, cancelPin, recover, refresh, error, result, pin, showPin, busy};')(...Object.values(dependencies))
  await mount()
  return { state, calls, storage, server, updates, exposed, unmount, template:descriptor.template.content }
}

test('real console setup persists the function click before a device target and keeps true repeat clicks', async () => {
  const { state, calls, server } = await consoleHarness()
  await state.choose(COMMANDS.find(c => c.type === 'SWITCH_TOTAL_NORMAL'))
  assert.equal(calls[0].action, 'function')
  assert.equal(state.result.value.pending.type, 'SWITCH_TOTAL_NORMAL')
  await state.target('switch', '1')
  assert.equal(calls[1].action, 'target')
  assert.equal(calls[1].target_id, '1')
  const a = state.press('D3DA'), b = state.press('D3DA')
  await Promise.all([a,b])
  assert.deepEqual(calls.map(c => c.sequence), [1,2,3,4])
  assert.notEqual(calls[2].event_id, calls[3].event_id)
  assert.equal(server.events.length, 4)
})

test('an uncertain request pauses operations and retry reuses its original event ID and sequence', async () => {
  const { state, calls, storage, exposed } = await consoleHarness({ failOnce:true })
  await state.press('D3DA')
  assert.ok(state.error.value)
  assert.equal(storage.size, 1)
  await state.press('D3DA')
  assert.equal(calls.length, 1)
  await assert.rejects(exposed.flush(), /同步/)
  await state.recover()
  assert.equal(calls[0].event_id, calls[1].event_id)
  assert.equal(calls[0].sequence, calls[1].sequence)
  assert.equal(state.error.value, '')
  assert.equal(storage.size, 0)
})

test('PIN passes only with the target request, never to persistent browser storage or click parameters', async () => {
  const { state, calls, storage } = await consoleHarness()
  await state.choose(COMMANDS.find(c => c.type === 'SIGNAL_SEAL'))
  assert.equal(state.showPin.value, true)
  state.pin.value = 'private-operator-pin'
  state.confirmPin()
  await state.target('signal', 'D3')
  assert.equal(calls[1].pin, 'private-operator-pin')
  assert.equal(state.pin.value, '')
  assert.equal(storage.size, 0)
  assert.ok(!JSON.stringify(persistableEvent(calls[1])).includes('private-operator-pin'))
  assert.equal(calls[0].pin, undefined)
})

test('reload restores an unconfirmed envelope and sends the same event instead of creating another click', async () => {
  const stored = eventEnvelope('button', 1, { button_id:'D3DA' }, 'fixed-event-id')
  const { state, calls } = await consoleHarness({ stored })
  assert.ok(state.error.value)
  await state.recover()
  assert.equal(calls[0].event_id, 'fixed-event-id')
  assert.equal(calls[0].sequence, 1)
})

test('restored sealed selection asks for the PIN again and cancel persists a cancellation event', async () => {
  const { state, calls } = await consoleHarness({ initialPending:{type:'SIGNAL_SEAL', target:'signal'} })
  assert.equal(state.showPin.value, true)
  await state.cancelPin()
  assert.equal(calls[0].action, 'cancel_selection')
  assert.equal(state.showPin.value, false)
  assert.equal(state.result.value.pending, null)
})

test('fixed block button captures the function first and the target after sealed confirmation', async () => {
  const { state, calls } = await consoleHarness()
  await state.block({ type:'BLOCK_ACCIDENT_RESET', fixedTarget:'XD', sealed:true })
  assert.equal(calls.length, 1)
  state.pin.value = 'test-pin'
  state.confirmPin()
  await new Promise(resolve => setTimeout(resolve, 0))
  assert.equal(calls[1].action, 'target')
  assert.equal(calls[1].target_id, 'XD')
  assert.equal(calls[1].target_kind, 'block')
})

const { operationPath, operationLocation, operationReturn, operationStatus, sessionStatus, operationError, draftErrors, canSaveRecording, publishIssues } = await import('../src/domain/operationPresentation.js')
const { pageNumber } = await import('../src/domain/pagination.js')
const operationBase = '/operations/manage'

test('late polling responses cannot roll the confirmed sequence back or reopen a stopped recording', async () => {
  const {state,exposed}=await consoleHarness()
  await state.press('D3DA')
  exposed.sync({status:'active',revision:0,snapshot:{}})
  assert.equal(state.result.value.revision,1)
  exposed.sync({status:'stopped',revision:1,snapshot:{}})
  exposed.sync({status:'active',revision:1,snapshot:{}})
  assert.equal(state.result.value.status,'stopped')
})

test('cancelling a sealed block clears its deferred target before confirming another sealed command', async () => {
  const { state, calls } = await consoleHarness()
  await state.block({ type:'BLOCK_ACCIDENT_RESET', fixedTarget:'XD', sealed:true })
  await state.cancelPin()
  await state.choose(COMMANDS.find(item => item.type === 'SIGNAL_SEAL'))
  state.pin.value = 'test-pin'; state.confirmPin()
  await new Promise(resolve => setTimeout(resolve, 0))
  assert.ok(!calls.some(item => item.action === 'target'))
  await state.target('signal', 'D3')
  assert.equal(calls.at(-1).target_id, 'D3')
})
const sample = (values = {}) => ({ id:1, version_id:11, owner_id:7, title:'调车进路', prompt:'办理 D3 至 D7 调车进路。', classes:['信号一班'], initial:{interval_available:true,occupied_sections:[]}, status:'draft', disabled:false, number:1, revision:3, standard_log:null, standard_session_id:null, versions:[{id:11,number:1,status:'draft'}], sessions:[], ...values })

async function flowHarness(view, options = {}) {
  const source = await readFile(new URL(`../src/views/teacher/${view}.vue`, import.meta.url), 'utf8')
  const descriptor = parse(source).descriptor, calls = [], guards = {}, pending = [], focus = []
  let stored = sample(options.question)
  const route = { path:operationPath(1), fullPath:operationPath(1), params:{questionId:'1'}, query:{}, ...options.route }
  const invoke = (name, fn) => async (...args) => { calls.push({name,args:structuredClone(args)}); return await fn(...args) }
  const api = {
    listOperations:invoke('list', async () => ({items:[stored],total:1})),
    getOperation:invoke('get', async () => structuredClone(stored)),
    getOperationVersion:invoke('version', async () => sample({version_id:10,number:0,status:'published'})),
    getOperationStation:invoke('station', async () => ({sections:[{name:'1DG'}]})),
    getOperationClasses:invoke('classes', async () => ({items:[{name:'信号一班',student_count:2},{name:'信号二班',student_count:1}],total:2})),
    deleteOperation:invoke('delete', async () => {}),
    updateOperation:invoke('update', async (id, data) => {
      stored = {...stored,...data,status:'draft',number:stored.status === 'published' ? stored.number + 1 : stored.number,revision:stored.revision+1}; return structuredClone(stored)
    }),
    createOperation:invoke('create', async data => {stored=sample(data);return structuredClone(stored)}),
    disableOperation:invoke('disable', async () => {}),
    publishOperation:invoke('publish', async () => {stored.status='published'}),
    startOperationSession:invoke('start', async (id, kind) => {
      stored.sessions.unshift({id:'new-session',kind,status:'active',owner_id:7,version_id:stored.version_id})
      return {session_id:'new-session',status:'active',snapshot:{session_kind:kind},events:[],revision:0}
    }),
    stopOperationSession:invoke('stop', async () => {stored.sessions.forEach(item => {item.status='stopped'});return {status:'stopped',snapshot:{session_kind:'recording'},events:[{}]}}),
    saveOperationStandard:invoke('saveStandard', async () => structuredClone(stored)),
    downloadOperationLog:invoke('download', async () => {}),
    ...options.api,
  }
  const dependencies = {
    computed, reactive, ref, paginate, pageNumber, initialForm, draftPayload,
    operationBase, operationPath, operationLocation, operationReturn, operationStatus, sessionStatus, operationError, draftErrors, canSaveRecording, publishIssues,
    nextTick:async () => {}, document:{getElementById:id => ({focus:() => focus.push(id)})},
    window:{addEventListener:() => {},removeEventListener:() => {}},
    watch:(getter, fn, config) => {if(config?.immediate)pending.push(fn())},
    onMounted:fn => pending.push(fn()), onBeforeUnmount:() => {}, onBeforeRouteLeave:fn => {guards.leave=fn}, onBeforeRouteUpdate:fn => {guards.update=fn},
    useRoute:() => route, useRouter:() => ({push:invoke('push', async () => {}),replace:invoke('replace', async () => {})}),
    useUserStore:() => ({role:'teacher',user:{id:7}}),
    ElMessageBox:{confirm:invoke('confirm', options.confirm || (async () => {}))}, ...api,
  }
  const exposed = {
    OperationQuestions:'rows,page,total,notice,search,filter,load,disable,remove,applyFilters',
    OperationEditor:'form,current,payload,dirty,errors,save,locked,notice,load,working,classOptions',
    OperationWorkspace:'current,task,sessionId,consoleResult,consoleRef,canSaveStandard,kind,isHistorical,load,start,finish,saveStandard,notice,working',
    OperationReview:'current,displayed,historical,issues,publish,notice,load,selectVersion',
  }[view]
  const state = new Function(...Object.keys(dependencies), descriptor.scriptSetup.content.replace(/^import .*$/gm, '') + `\nreturn {${exposed}};`)(...Object.values(dependencies))
  await Promise.all(pending)
  return {state,calls,route,guards,focus,template:descriptor.template.content}
}

test('library forwards page, title/class search and status to the server', async () => {
  const {state,calls} = await flowHarness('OperationQuestions', {route:{path:operationBase,fullPath:operationBase+'?page=2&search=班&status=draft',params:{},query:{page:'2',search:'班',status:'draft'}}})
  assert.deepEqual(calls.find(item=>item.name==='list').args,[2,{search:'班',status:'draft'}])
  assert.equal(state.rows.value.length,1)
  state.search.value='调车'; state.filter.value='published'; state.applyFilters()
  assert.deepEqual(calls.findLast(item=>item.name==='push').args,[{path:operationBase,query:{search:'调车',status:'published'}}])
})

test('old question/session links redirect into the independent workspace without creating a session', async () => {
  const {calls} = await flowHarness('OperationQuestions',{route:{path:operationBase,fullPath:operationBase+'?question=1&session=sid',params:{},query:{question:'1',session:'sid'}}})
  assert.deepEqual(calls.find(item=>item.name==='replace').args,[{path:operationPath(1,'record'),query:{session:'sid'}}])
  assert.ok(!calls.some(item=>['list','start'].includes(item.name)))
})

test('cancelling disable leaves the question and notice untouched', async () => {
  const {state,calls} = await flowHarness('OperationQuestions',{confirm:async()=>{throw 'cancel'}})
  await state.disable(sample())
  assert.ok(!calls.some(item=>item.name==='disable'))
  assert.equal(state.notice.value,'')
})

test('editor saves optimistic revision and de-duplicates classes, then continues in a separate recording page', async () => {
  const {state,calls} = await flowHarness('OperationEditor',{question:{status:'published'}})
  assert.equal(state.dirty.value,false)
  state.form.title='新的题设';state.form.classes=['信号一班','信号二班','信号一班']
  assert.equal(state.dirty.value,true)
  await state.save(true)
  const body=calls.find(item=>item.name==='update').args[1]
  assert.equal(body.revision,3);assert.equal(body.title,'新的题设')
  assert.deepEqual(body.classes,['信号一班','信号二班'])
  assert.equal(state.current.value.number,2);assert.equal(state.current.value.status,'draft')
  assert.equal(state.dirty.value,false)
  assert.deepEqual(calls.findLast(item=>item.name==='push').args,[operationLocation(1,'record')])
  assert.ok(!calls.some(item=>item.name==='start'))
})

test('incomplete drafts can be saved; continue validates beside the fields and focuses the first error', async () => {
  const {state,calls,focus} = await flowHarness('OperationEditor',{route:{path:operationBase+'/new',params:{},query:{}}})
  await state.save(true)
  assert.deepEqual(Object.keys(state.errors.value),['title','prompt','classes'])
  assert.deepEqual(focus,['operation-title'])
  assert.ok(!calls.some(item=>item.name==='create'))
  await state.save(false)
  assert.ok(calls.some(item=>item.name==='create'))
  assert.equal(state.dirty.value,false)
})

test('editor guards unsaved navigation and prevents edits during a persisted active session', async () => {
  const first=await flowHarness('OperationEditor',{confirm:async()=>{throw 'cancel'}})
  first.state.form.prompt='未保存的任务'
  assert.equal(await first.guards.leave(),false)
  const second=await flowHarness('OperationEditor',{question:{sessions:[{id:'sid',owner_id:7,version_id:11,status:'active'}]}})
  assert.equal(second.state.locked.value,true)
  await second.state.save(true)
  assert.ok(!second.calls.some(item=>item.name==='update'))
})

test('workspace resumes the persisted session on refresh without implicitly starting another recording', async () => {
  const {state,calls}=await flowHarness('OperationWorkspace',{route:{query:{session:'sid'}},question:{sessions:[{id:'sid',owner_id:7,kind:'recording',status:'active',version_id:11}]}})
  assert.equal(state.sessionId.value,'sid')
  assert.equal(state.kind.value,'recording')
  assert.ok(!calls.some(item=>item.name==='start'))
})

test('entering a workspace also restores an existing active session into the URL', async () => {
  const {state,calls}=await flowHarness('OperationWorkspace',{question:{sessions:[{id:'persisted',owner_id:7,kind:'preview',status:'active',version_id:11}]}})
  assert.equal(state.sessionId.value,'persisted')
  assert.equal(state.kind.value,'preview')
  assert.deepEqual(calls.find(item=>item.name==='replace').args,[{path:operationPath(1),query:{session:'persisted'}}])
  assert.ok(!calls.some(item=>item.name==='start'))
})

test('stopping flushes confirmed clicks before stop, syncs the child and then reloads the question', async () => {
  const {state,calls}=await flowHarness('OperationWorkspace',{route:{query:{session:'sid'}},question:{sessions:[{id:'sid',owner_id:7,kind:'recording',status:'active',version_id:11}]}})
  state.consoleResult.value={status:'active'}
  state.consoleRef.value={flush:async()=>calls.push({name:'flush'}),sync:()=>calls.push({name:'sync'})}
  calls.length=0
  await state.finish()
  assert.deepEqual(calls.map(item=>item.name),['flush','stop','sync','get'])
  assert.equal(state.consoleResult.value.status,'stopped')
})

test('an unconfirmed click blocks stopping and leaving instead of losing the pending request', async () => {
  const {state,calls,guards}=await flowHarness('OperationWorkspace')
  state.consoleResult.value={status:'active'}
  state.consoleRef.value={flush:async()=>{throw new Error('请先同步未确认的操作')}}
  await state.finish()
  assert.ok(!calls.some(item=>item.name==='stop'))
  assert.equal(await guards.leave(),false)
  assert.match(state.notice.value,/同步/)
})

test('only a nonempty stopped recording of the current draft can save and proceed to review', async () => {
  const {state,calls}=await flowHarness('OperationWorkspace',{route:{query:{session:'sid'}},question:{sessions:[{id:'sid',owner_id:7,kind:'recording',status:'stopped',version_id:11}]}})
  state.consoleRef.value={flush:async()=>calls.push({name:'flush'})}
  state.consoleResult.value={status:'stopped',snapshot:{session_kind:'recording'},events:[]}
  assert.equal(state.canSaveStandard.value,false)
  state.consoleResult.value.events=[{action:'button'}]
  assert.equal(state.canSaveStandard.value,true)
  await state.saveStandard()
  assert.deepEqual(calls.slice(-3).map(item=>item.name),['flush','saveStandard','push'])
  assert.deepEqual(calls.findLast(item=>item.name==='push').args,[operationLocation(1,'review')])
  state.consoleResult.value.snapshot.session_kind='preview'
  assert.equal(state.canSaveStandard.value,false)
  state.consoleResult.value.snapshot.session_kind='recording';state.current.value.status='published'
  assert.equal(state.canSaveStandard.value,false)
  state.current.value.status='draft';state.current.value.disabled=true
  assert.equal(state.canSaveStandard.value,false)
  state.current.value.disabled=false;state.current.value.version_id=12
  assert.equal(state.canSaveStandard.value,false)
})

test('old recordings show the matching historical task and never offer current-standard save', async () => {
  const {state,calls}=await flowHarness('OperationWorkspace',{route:{query:{session:'old'}},question:{number:2,version_id:12,versions:[{id:11,number:1,status:'published'},{id:12,number:2,status:'draft'}],sessions:[{id:'old',owner_id:7,kind:'recording',status:'stopped',version_id:11}]},api:{getOperationVersion:async()=>sample({number:1,title:'旧题面'})}})
  assert.equal(state.isHistorical.value,true);assert.equal(state.task.value.title,'旧题面')
  state.consoleResult.value={status:'stopped',snapshot:{session_kind:'recording'},events:[{}]}
  assert.equal(state.canSaveStandard.value,false)
  await state.start();await state.saveStandard()
  assert.ok(!calls.some(item=>['start','saveStandard'].includes(item.name)))
})

test('preview explicitly starts through the preview API and cancelled restart is silent', async () => {
  const {state,calls}=await flowHarness('OperationWorkspace',{route:{query:{mode:'preview'}},confirm:async()=>{throw 'cancel'}})
  await state.start()
  assert.deepEqual(calls.find(item=>item.name==='start').args,[1,'preview'])
  assert.equal(state.sessionId.value,'new-session')
  await state.start()
  assert.equal(calls.filter(item=>item.name==='start').length,1)
  assert.equal(state.notice.value,'')
})

test('review cannot publish historical versions or a draft with an active console', async () => {
  const past=await flowHarness('OperationReview',{route:{query:{version:'1'}},question:{number:2,version_id:12},api:{getOperationVersion:async()=>sample({title:'旧题面',status:'published'})}})
  assert.equal(past.state.historical.value,true)
  await past.state.publish()
  assert.ok(!past.calls.some(item=>item.name==='publish'))
  const active=await flowHarness('OperationReview',{question:{standard_session_id:'sid',standard_log:[{action:'button',result:{accepted:true}}],sessions:[{version_id:11,status:'active'}]}})
  assert.ok(active.state.issues.value.some(item=>item.includes('结束')))
  await active.state.publish()
  assert.ok(!active.calls.some(item=>item.name==='publish'))
})

test('review confirms destination classes, publishes, reloads and reports the resulting state', async () => {
  const {state,calls}=await flowHarness('OperationReview',{question:{standard_session_id:'sid',standard_log:[{action:'button',result:{accepted:true}}]}})
  assert.deepEqual(state.issues.value,[])
  await state.publish()
  assert.match(calls.find(item=>item.name==='confirm').args[0],/信号一班/)
  assert.deepEqual(calls.slice(-3).map(item=>item.name),['confirm','publish','get'])
  assert.equal(state.current.value.status,'published')
  assert.match(state.notice.value,/已发布/)
})

test('student catalogue exposes only the released list and enters S4 through the guarded begin API', async () => {
  const source=await readFile(new URL('../src/views/student/OperationCatalogue.vue',import.meta.url),'utf8')
  assert.ok(!source.includes('OperationConsole'));assert.ok(!source.includes('standard_log'))
  assert.ok(source.includes('await beginLearning(question.id)'))
  assert.ok(source.includes('/student/learn/operations/attempts/'))
  assert.ok(!source.includes('暂未开放作答'))
})

test('all S3 subpages have accurate breadcrumbs without changing the role menus', async () => {
  const {pageLabel}=await import('../src/ui/navigation.js')
  assert.equal(pageLabel(operationBase,'teacher'),'操作题管理')
  assert.equal(pageLabel(operationBase+'/new','admin'),'题目设置')
  assert.equal(pageLabel(operationPath(1),'teacher'),'题目设置')
  assert.equal(pageLabel(operationPath(1,'review'),'teacher'),'检查与发布')
  assert.equal(pageLabel(operationPath(1,'record'),'admin'),'站场操作台')
})

test('the editing and recording flow carries the original library page and filters without allowing an external return', async () => {
  const back=operationBase+'?page=2&search=%E8%B0%83%E8%BD%A6&status=draft'
  const editor=await flowHarness('OperationEditor',{route:{query:{back}}})
  await editor.state.save(true)
  assert.deepEqual(editor.calls.findLast(item=>item.name==='push').args,[{path:operationPath(1,'record'),query:{back}}])
  assert.equal(operationReturn('https://example.com/'),operationBase)
  assert.equal(operationReturn('/operations/manage/new'),operationBase)
  assert.equal(operationReturn(back),back)
})

test('real router keeps the workspace outside the campus shell and enforces manager authentication on every S3 route', async () => {
  const {createRouter,createMemoryHistory}=await import('vue-router')
  const {roleHomeMap}=await import('../src/ui/navigation.js')
  const source=await readFile(new URL('../src/router/index.js',import.meta.url),'utf8')
  const user={role:'teacher',isLoggedIn:true}
  const script=source.replace(/^import .*$/gm,'').replace(/^export \{.*\}$/gm,'').replace(/import\('[^']+'\)/g,'Promise.resolve({render:()=>null})').replace('export default router','return router')
  const router=new Function('createRouter','createWebHistory','AppLayout','useUserStore','roleHomeMap',script)(createRouter,createMemoryHistory,{},()=>user,roleHomeMap)
  for(const path of [operationBase,operationBase+'/new',operationPath(1),operationPath(1,'review'),operationPath(1,'record')]) {
    await router.push(path)
    assert.equal(router.currentRoute.value.path,path)
  }
  assert.equal(router.currentRoute.value.matched.length,1)
  assert.equal(router.currentRoute.value.meta.requiresAuth,true)
  user.role='student'
  await router.push(operationPath(1,'review'))
  assert.equal(router.currentRoute.value.path,'/student/dashboard')
  user.isLoggedIn=false
  await router.push(operationPath(1,'record'))
  assert.equal(router.currentRoute.value.path,'/login')
  assert.equal(router.currentRoute.value.query.redirect,operationPath(1,'record'))
})

test('the authoring class dropdown loads real student classes before any class is selected', async () => {
  const {state,calls}=await flowHarness('OperationEditor',{route:{path:operationBase+'/new',params:{},query:{}}})
  assert.equal(state.form.classes.length,0)
  assert.deepEqual(state.classOptions.value.map(item=>item.name),['信号一班','信号二班'])
  assert.ok(calls.some(item=>item.name==='classes'))
  assert.match(state.classOptions.value[0].label,/2 人/)
})

test('existing class settings remain visible when their students have left the course', async () => {
  const {state}=await flowHarness('OperationEditor',{question:{classes:['往届班级']}})
  assert.ok(state.classOptions.value.some(item=>item.name==='往届班级'))
  assert.deepEqual(state.form.classes,['往届班级'])
})

test('delete requires confirmation, refreshes the list, and cancelling does not send a delete', async () => {
  const accepted=await flowHarness('OperationQuestions')
  await accepted.state.remove(sample())
  assert.deepEqual(accepted.calls.slice(-3).map(item=>item.name),['confirm','delete','list'])
  assert.match(accepted.calls.find(item=>item.name==='confirm').args[0],/无法恢复/)
  const cancelled=await flowHarness('OperationQuestions',{confirm:async()=>{throw 'cancel'}})
  await cancelled.state.remove(sample())
  assert.ok(!cancelled.calls.some(item=>item.name==='delete'))
  assert.equal(cancelled.state.notice.value,'')
})

test('another teachers recording can be opened but cannot be stopped, restarted or saved as an answer', async () => {
  const {state,calls,guards}=await flowHarness('OperationWorkspace',{route:{query:{session:'shared'}},question:{sessions:[{id:'shared',owner_id:9,version_id:11,kind:'recording',status:'active'}]}})
  assert.equal(state.sessionId.value,'shared')
  state.consoleResult.value={status:'active',read_only:true,snapshot:{session_kind:'recording'},events:[{}]}
  await state.start();await state.finish()
  assert.equal(await guards.leave(),true)
  state.consoleResult.value.status='stopped'
  assert.equal(state.canSaveStandard.value,false)
  await state.saveStandard()
  assert.ok(!calls.some(item=>['start','stop','saveStandard','confirm'].includes(item.name)))
})
