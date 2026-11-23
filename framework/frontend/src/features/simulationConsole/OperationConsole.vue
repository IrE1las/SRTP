<template>
  <section class="record-console">
    <div v-if="error" class="console-error" role="alert"><span>{{ error }}</span><el-button :loading="working" @click="recover">同步并重试</el-button></div>
    <SimulationConsole ref="board" :client="client" :read-only="readOnly || pausePending || !!error || result?.read_only || result?.status !== 'active'" :exam-mode="examMode" embedded />
  </section>
</template>
<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import SimulationConsole from './SimulationConsole.vue'
import { getOperationStation, getOperationSession, postOperationEvent } from '@/api/operations'
import { eventEnvelope, persistableEvent } from '@/domain/operationEvents'
import { mergeConsole } from '@/domain/operationConsole'
const props=defineProps({sessionId:{type:String,required:true},readOnly:Boolean,api:{type:Object,default:null},examMode:Boolean,pausePending:Boolean})
const emit=defineEmits(['update'])
const board=ref(null),result=ref(null),error=ref(''),working=ref(false)
const key=`srtp-operation-pending-${props.sessionId}`,frames=[]
let queue=Promise.resolve(),outstanding=null,disposed=false
try{outstanding=JSON.parse(sessionStorage.getItem(key)||'null');if(outstanding)error.value='存在尚未确认的操作，请同步并重试。'}catch{sessionStorage.removeItem(key)}
function accept(data){
 if(result.value && (data.revision<result.value.revision || result.value.status!=='active' && data.status==='active'))return result.value.snapshot
 if(result.value && data.revision===result.value.revision && (data.state_version??data.snapshot?.version??0)<(result.value.state_version??result.value.snapshot?.version??0))return result.value.snapshot
 result.value=data.snapshot?data:mergeConsole(result.value,data)
 const snap=result.value.snapshot
 if(snap && frames.at(-1)?.version!==snap.version){frames.push(JSON.parse(JSON.stringify(snap)));if(frames.length>200)frames.shift()}
 emit('update',result.value);return snap
}
async function load(){const data=await(props.api?.console||getOperationSession)(props.sessionId);return accept(data)}
function send(action,values={}){
 queue=queue.then(async()=>{
  if(disposed||props.pausePending||outstanding||result.value?.read_only||result.value?.status!=='active')throw Error('当前操作台不可操作')
  working.value=true
  try{
   const event=eventEnvelope(action,result.value.revision+1,values)
   const saved=persistableEvent(event)
   sessionStorage.setItem(key,JSON.stringify(saved));outstanding=saved
   const data=await(props.api?.event||postOperationEvent)(props.sessionId,event)
   const snapshot=accept(data);sessionStorage.removeItem(key);outstanding=null
   return{...data.event.result,snapshot}
  }
  catch(e){error.value=e.response?.data?.detail||(outstanding?'操作尚未确认，请同步并重试。':'无法在浏览器保存本次操作，请同步后重试。');throw e}
  finally{working.value=false}
 });const task=queue;queue=task.catch(()=>{});return task
}
const switchCommands=new Set(['SWITCH_TOTAL_NORMAL','SWITCH_TOTAL_REVERSE','SWITCH_SINGLE_LOCK','SWITCH_SINGLE_UNLOCK','SWITCH_SEAL','SWITCH_UNSEAL','SET_SWITCH_INDICATION','RESTORE_SWITCH_INDICATION'])
const sectionCommands=new Set(['SET_SECTION_OCCUPANCY','CLEAR_SECTION_OCCUPANCY','SECTION_FAULT_UNLOCK','SIMULATE_TRAIN_START'])
const client={
 storageKey:`operation-${props.sessionId}`,
 getStationPackage:()=> (props.api?.station||getOperationStation)(),
 loadSession:load,getSimulationSnapshot:load,
 getSimulationReplay:async()=>frames.map(s=>JSON.parse(JSON.stringify(s))),
 pressStationButton:(_id,button)=>send('button',{button_id:button}),
 clearStationSelection:()=>send('function',{button_id:'CLEAR_SELECTION'}),
 selectFunction:command=>send('function',{button_id:command.type}),
 cancelFunction:()=>send('cancel_selection'),
 operateConsole:(_id,command)=>send('command',{button_id:command.type,target_id:command.target,
   target_kind:switchCommands.has(command.type)?'switch':sectionCommands.has(command.type)?'section':command.type.startsWith('BLOCK_')?'block':'signal',parameters:command.payload||{},pin:command.pin||null}),
}
async function recover(){
 working.value=true
 try{
  await load()
  if(outstanding){
   if(outstanding.sequence>result.value.revision){
    // Retrying sealed operations requires a fresh PIN; never persist it.
    if(result.value.pending && ['MANUAL_UNLOCK_ROUTE','SECTION_FAULT_UNLOCK','GUIDE_ARM','GUIDE_TOTAL_LOCK','GUIDE_TOTAL_UNLOCK','SIGNAL_SEAL','SIGNAL_UNSEAL','SIGNAL_LIGHT_OFF','BLOCK_ACCIDENT_RESET','BLOCK_TOTAL_AUX','BLOCK_DEPARTURE_AUX','BLOCK_RECEPTION_AUX'].includes(outstanding.button_id)){
     const {ElMessageBox}=await import('element-plus')
     const answer=await ElMessageBox.prompt('教学操作口令','重试操作',{inputType:'password'})
     accept(await(props.api?.event||postOperationEvent)(props.sessionId,{...outstanding,pin:answer.value}))
    }else accept(await(props.api?.event||postOperationEvent)(props.sessionId,outstanding))
   }
   outstanding=null;sessionStorage.removeItem(key)
  }
  error.value=''
 }catch(e){error.value=e.response?.data?.detail||'同步失败，请重试。'}finally{working.value=false}
}
const hasUnconfirmed=computed(()=>working.value||!!outstanding||!!board.value?.busy)
defineExpose({hasUnconfirmed,sync:data=>{const snap=accept(data);board.value?.sync(snap)},flush:async()=>{await board.value?.flush();await queue;if(outstanding||error.value)throw Error('请先同步未确认的操作');return result.value}})
onBeforeUnmount(()=>{disposed=true})
</script>
<style scoped>
.record-console{position:relative;flex:1;display:flex;flex-direction:column;min-height:0}.record-console :deep(.simulation-page){flex:1;min-height:0}.record-console :deep(.console-shell){height:100%;min-height:620px;flex:1}.console-error{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:10px 14px;background:#fff1e7;color:#9b4423}
.record-console :deep(.console-shell:fullscreen),.record-console :deep(.console-shell.window-fullscreen){height:100dvh;min-height:0}
</style>
