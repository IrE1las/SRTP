<template>
  <div class="simulation-page">
    <div v-if="!embedded" class="page-intro">
      <div><h1>联锁仿真操作台</h1>
</div>

    </div>
    <div ref="consoleRoot" class="console-shell" :class="{'window-fullscreen':fallbackFullscreen}" v-loading="loading">
      <nav class="console-menu" aria-label="操作台菜单">
        <strong>{{ station?.station_name || '联锁仿真' }}</strong><span class="mode-label">教学仿真</span>
        <button @click="showRoutes = !showRoutes">进路与核对</button>
        <button @click="replaying ? closeReplay() : openReplay()">{{ replaying ? '返回实时' : '操作回放' }}</button>
        <button :aria-pressed="contextPicking" :class="{ 'menu-picking':contextPicking }" :disabled="replaying || busy || stale" @click="toggleContextPicking">设备菜单</button>
        <button @click="showHelp = !showHelp">操作说明</button><button class="fullscreen-button" :disabled="examMode" @click="toggleFullscreen">{{ isFullscreen ? '退出全屏' : '全屏站场' }}</button>
      </nav>
      <div v-if="loadError" class="load-error" role="alert">{{ loadError }}<button @click="boot">重试加载</button></div>
      <div v-if="replaying" class="replay-bar"><strong>只读回放</strong><input v-model.number="replayIndex" type="range" min="0" :max="Math.max(0,replayFrames.length-1)" aria-label="回放时间轴" /><span>{{ replayIndex+1 }} / {{ replayFrames.length }}</span><button @click="closeReplay">结束回放</button></div>
      <div class="console-body"><div v-if="station" class="stage-wrap">
        <ReferenceStationDiagram :station="station" :snapshot="displaySnapshot" :selected="displaySnapshot?.selected_buttons || []" :targeting="pending?.target" :context-picking="contextPicking" console-mode
          @press="pressButton" @inspect="inspectDevice" @group="selectGroup" @signal="selectSignal" @block="chooseCommand" @context="openContext" @guide="pressGuide" />
        <section class="alarm-region" :class="{ alarming: alarms.length }" aria-label="报警信息区" aria-live="polite">
          <header>报警信息 <button @click="acknowledgeAlarms" title="确认已阅读的报警，记录仍保留在回放中">确认</button></header>
          <div v-if="!alarms.length" class="no-alarm">无未确认报警</div><div v-for="event in alarms" :key="event.version" class="alarm-line"><time>{{ eventTime(event.time) }}</time> {{ event.message }}</div>
        </section>
        <section class="equipment-region" aria-label="设备状态信息区">
          <div><span>联锁仿真</span><b :class="{ failed: stale }">{{ stale ? '连接中断' : '运行' }}</b></div><div><span>操作会话</span><b>{{ replaying ? '回放' : '操作' }}</b></div><div><span>故障设备</span><b :class="{ failed: faultCount }">{{ faultCount }}</b></div>
        </section>
        <div v-if="showHelp" class="help-panel"><strong>操作顺序</strong><button @click="showHelp = false" aria-label="关闭操作说明">×</button>
          <p>列车：先点绿色列车按钮，再点终端列车按钮。调车：依次点击始端、终端信号灯。</p>
          <p>操纵道岔：先按“总定位 / 总反位 / 单锁 / 单解”，再点道岔编号；双动道岔整组执行。</p>
          <p>总取消、总人解和重开信号：先按功能按钮，再点原进路的始端信号。功能按钮 15 秒未选择目标自动复原。</p>
          <p>带铅封操作须输入教学口令，默认 0000。人工解锁期间信号关闭、锁闭保持，倒计时完成且区段空闲后释放。</p>
          <p>空闲灰色，锁闭白色，占用红色；行车出清先显示绿色，1 秒后转灰。定位绿色，反位黄色，失表示红闪。</p><p v-if="client.loadSession">操作会保存；重新进入可继续，提交或结束后只能查看。</p><p v-else>自由操作不写入实验学习记录；当前会话可回放，服务重启后需重新开始。</p>
          <p>本站提供 {{ station.counts.candidate_routes }} 条进路定义。通过按钮以 TA 标识；列车变通选路可点击中间调车信号（DA），再点列车终端。同按钮多路径按可用条件选排。</p>
          <p>深蓝色引导按钮位于进站列车按钮旁。先将接车路径道岔就位，再按对应引导按钮、确认口令，按现有道岔位置确定接车股道，无需点击终端。内方首区段故障时，须在 15 秒内再次按引导按钮保持；该区段恢复空闲后不再倒计时。</p>
          <p>道岔失表示等情况下，须先人工确认接车路径安全，按 X／S 引导总锁、确认口令，再按对应进站引导按钮开放红白灯；不需选择终端。总人解可关闭引导信号，总锁仍保持；再次按对应引导总锁并确认口令才能解除。</p>
          <p>Ctrl＋右键道岔、DG、股道或无岔接近区段，可启动经过该区段的进路自动行车，每 2 秒按行车方向跨越一个绝缘区段。红色仅沿进路白色光带显示。无岔区段还可设置占用、故障、出清；信号机可设置断丝或恢复灯丝。</p>
          <p>移动端先按“设备菜单”，再点道岔、信号机、股道或闭塞框，即可打开同样的菜单；每次选中后自动退出，按 Esc 或再次按按钮可取消。双动道岔整组设置和恢复表示，任一端在进路内时禁止设置整组失表示。灯丝断丝时引导仍可办理，但信号不能点亮。</p>
          <p>区故解先确认区段恢复空闲，再按功能、输入口令、点击区段。Ctrl＋右键点击对应闭塞框可模拟邻站同意；<template v-if="createSimulationSession">点击站场空白处可新建会话。</template><template v-else>本题会话通过页面的开始、结束或提交按钮管理。</template></p>
        </div>
      </div></div>
      <div class="function-region" aria-label="常用功能按钮区">
        <button v-for="command in visibleCommands" :key="command.label" class="function-button" :class="{ sealed: command.sealed, pressed: command.active || pending?.type === command.type && !command.unavailable }"
          :disabled="readOnly || busy || replaying || stale || !!command.unavailable" :title="command.unavailable || command.label" :aria-pressed="command.active || pending?.type === command.type && !command.unavailable" @click="chooseCommand(command)">
          {{ command.label }}
        </button>
      </div>
      <div class="hint-region" aria-label="提示信息区" aria-live="polite"><span>{{ contextPicking ? '设备菜单：请点击道岔、信号机、股道或闭塞框' : pending ? `${pending.label}：请选择${targetLabel(pending.target)}（${pendingRemaining}秒）` : displaySnapshot?.selected_buttons?.length ? `已选 ${displaySnapshot.selected_buttons.join(' → ')}，等待下一按钮（${displaySnapshot.selection_remaining_seconds}秒）` : displaySnapshot?.last_message || '等待操作' }}</span><time aria-label="时钟信息区">{{ clockText }}</time></div>
      <div v-if="pinCommand" class="pin-backdrop" @keydown.esc="cancelPin"><form class="pin-dialog" role="dialog" aria-modal="true" aria-labelledby="pin-title" @submit.prevent="confirmPin">
        <strong id="pin-title">{{ pinCommand.label }} · 口令确认</strong><p>{{ pinCommand.type === 'GUIDE_TOTAL_LOCK' ? '须先人工确认该咽喉道岔位置、接车路径和行车条件安全。请输入口令建立引导总锁。' : pinCommand.type === 'GUIDE_TOTAL_UNLOCK' ? '须先关闭引导信号，确认列车完整进入股道、咽喉出清。请输入口令解除引导总锁。' : pinCommand.fixedTarget ? `请输入教学操作口令，确认操作 ${pinCommand.fixedTarget}。` : '请输入教学操作口令，然后选择目标设备。' }}</p><input ref="pinInput" v-model="pin" type="password" maxlength="32" autocomplete="off" aria-label="教学操作口令" />
        <small>默认教学口令为 0000；可由管理员通过服务器配置修改。</small><div><button type="button" @click="cancelPin">取消</button><button type="submit">确认</button></div>
      </form></div>
    <ConsoleContextMenu v-if="contextMenu" :key="contextMenu.key" v-bind="contextMenu" :items="contextItems" @choose="chooseContext" @close="closeContext" />
    <div v-if="showSessionSettings" class="pin-backdrop" @keydown.esc="showSessionSettings=false"><form class="pin-dialog" role="dialog" aria-modal="true" aria-label="新建仿真会话" @submit.prevent="newSession">
      <strong>新建仿真会话</strong><p>新会话独立开始，当前会话的进路不会因此解锁。</p>
      <label>初始区间许可 <select v-model="intervalAvailable"><option :value="true">已具备</option><option :value="false">未具备</option></select></label>
      <div><button type="button" @click="showSessionSettings=false">取消</button><button type="submit" :disabled="busy">{{ confirmNew ? '确认新建' : '新建会话' }}</button></div>
    </form></div>
    <section v-if="showRoutes && station" class="route-audit"><div class="activity-heading"><strong>{{ '标准站进路' }}</strong><span>可解析办理 {{ station.counts.ready_routes }} · 数据异常 {{ station.counts.blocked_routes }} · 共 {{ station.counts.candidate_routes }}</span></div>
      <p v-if="!station.routes">学生可在站场自由操作；完整进路条件和核对清单由教师查看。</p>
      <template v-else><label>查找进路<input v-model="routeQuery" placeholder="如 XD、D3、S5" /></label><div class="audit-scroll"><table><thead><tr><th>进路</th><th>按钮顺序</th><th>状态 / 来源</th></tr></thead><tbody><tr v-for="route in filteredRoutes" :key="route.id"><td>{{ route.name || route.id }}</td><td>{{ route.button_sequence.join(' → ') }}</td><td :class="{ 'audit-blocked':route.status!=='ready' }">{{ route.status === 'ready' ? '可办理' : route.reasons.join('；') }}<template> · 原文件第 {{ route.source_row }} 行<span v-for="warning in route.warnings" :key="warning">；{{ warning }}</span></template></td></tr></tbody></table></div></template>
    </section>
    </div>
  </div>
</template>

<script setup>
import { useConsoleFullscreen } from './useConsoleFullscreen'
import './consoleLayout.css'
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/store/user'
import ReferenceStationDiagram from './ReferenceStationDiagram.vue'
import ConsoleContextMenu from './ConsoleContextMenu.vue'
import { consoleCommands } from './consoleCommands'
import { matchingTrainRoutes } from './consoleContext'
import * as freeClient from './api'
const props=defineProps({client:{type:Object,default:null},embedded:Boolean,readOnly:Boolean,examMode:Boolean})
const client=props.client || freeClient
const { clearStationSelection, createSimulationSession, getSimulationReplay, getSimulationSnapshot, getStationPackage, operateConsole, pressStationButton }=client
const userStore=useUserStore(), consoleRoot=ref(null), station=ref(null), snapshot=ref(null)
const {isFullscreen,fallbackFullscreen,toggleFullscreen}=useConsoleFullscreen(consoleRoot)
const loading=ref(true), busy=ref(false), stale=ref(false), loadError=ref('')
const showRoutes=ref(false), showHelp=ref(false), intervalAvailable=ref(true), confirmNew=ref(false), showSessionSettings=ref(false), contextMenu=ref(null)
const replaying=ref(false), replayFrames=ref([]), replayIndex=ref(0), acknowledged=ref(0), routeQuery=ref('')
const pending=ref(null), pinCommand=ref(null), pin=ref(''), pinInput=ref(null), now=ref(Date.now())
const contextPicking=ref(false)
let poller, ticker, lastPoll=0, disposed=false
let commandQueue=Promise.resolve()
const storageKey=computed(()=>`${client.storageKey || 'srtp-console-reference'}-${userStore.user?.id || 'anonymous'}`)
const canControlTrain=computed(()=>['student','teacher','admin'].includes(userStore.role))
const visibleCommands=computed(()=>consoleCommands(displaySnapshot.value?.guide_locks || []))
const displaySnapshot=computed(()=>replaying.value ? replayFrames.value[replayIndex.value] : snapshot.value)
const activeRoutes=computed(()=>(displaySnapshot.value?.routes || []).filter(r=>!['released','cancelled'].includes(r.status)))
const alarms=computed(()=>(displaySnapshot.value?.events || []).filter(e=>e.version>acknowledged.value && (e.kind==='rejected' || ['SET_SWITCH_INDICATION','signal_close','switch_timeout','route_setting_failed'].includes(e.kind))).slice(-8).reverse())
const faultCount=computed(()=>Object.values(displaySnapshot.value?.switches || {}).filter(s=>s.represented===false && !s.moving).length+Object.values(displaySnapshot.value?.sections || {}).filter(s=>s.occupancy_kind==='fault').length+Object.values(displaySnapshot.value?.signals || {}).filter(s=>s.filament_ok===false).length)
const clockText=computed(()=>new Date(now.value).toLocaleString('zh-CN',{hour12:false,timeZone:'Asia/Shanghai'}))
const pendingRemaining=computed(()=>Math.max(0,Math.ceil(((pending.value?.deadline || 0)-now.value)/1000)))
const filteredRoutes=computed(()=>(station.value?.routes || []).filter(r=>`${r.name || r.id} ${r.button_sequence.join(' ')}`.toLowerCase().includes(routeQuery.value.toLowerCase())))
const notify=message=>ElMessage.info(message)
const eventTime=value=>new Date(value).toLocaleTimeString('zh-CN',{hour12:false,timeZone:'Asia/Shanghai'})
const targetLabel=target=>({switch:'道岔编号',signal:'信号机',route:'原进路始端信号',section:'轨道区段'})[target] || '设备'
const contextItems=computed(()=>{
  const menu=contextMenu.value
  if(!menu)return []
  const disabled=props.readOnly || busy.value || stale.value || replaying.value || !canControlTrain.value
  const item=(label,type,target,payload={})=>({label,type,target,payload,disabled})
  if(menu.type==='background')return [{label:'新建仿真会话…',action:'session',disabled:disabled || !createSimulationSession}]
  if(menu.type==='block')return [{...item('模拟邻站同意','BLOCK_PEER_ACCEPT',menu.id),disabled:disabled || !['requested','awaiting_peer'].includes(snapshot.value?.blocks?.[menu.id]?.phase)}]
  if(menu.type==='signal')return [item('灯丝断丝','SIGNAL_FILAMENT_BREAK',menu.id),item('灯丝完好','SIGNAL_FILAMENT_RESTORE',menu.id),{separator:true},{label:'清除按钮',action:'clear',disabled}]
  const section=menu.section
  const tracks=[item(menu.type==='point'?`${section} 占用`:'股道占用','SET_SECTION_OCCUPANCY',section,{kind:'vehicle'}),item(menu.type==='point'?`${section} 故障`:'股道故障','SET_SECTION_OCCUPANCY',section,{kind:'fault'}),item(menu.type==='point'?`${section} 出清`:'股道出清','CLEAR_SECTION_OCCUPANCY',section)]
  const routes=matchingTrainRoutes(activeRoutes.value,section)
  const trains=routes.length?routes.map(r=>({...item(`${r.auto_running?'模拟行车中':'模拟行车'} · ${r.name || r.route_id}`,'SIMULATE_TRAIN_START',section,{route_instance_id:r.id}),disabled:disabled || r.auto_running || ['setting','track_proving','cancelling','clearing','manual_unlocking','closed_locked'].includes(r.status)})):[{label:'模拟行车（无对应进路）',disabled:true}]
  if(menu.type==='section')return [...tracks,{separator:true},...trains]
  const loss=item('道岔失去表示','SET_SWITCH_INDICATION',menu.id)
  if(snapshot.value?.switches?.[menu.id]?.indication_fault_allowed===false){loss.disabled=true;loss.reason='道岔组任一端在进路内，不能设置整组失表示'}
  return [loss,item('定位恢复表示','RESTORE_SWITCH_INDICATION',menu.id,{position:0}),item('反位恢复表示','RESTORE_SWITCH_INDICATION',menu.id,{position:1}),{separator:true},...tracks,{separator:true},...trains]
})
function closeContext(){contextMenu.value=null}
function toggleContextPicking(){closeContext();clearPending();contextPicking.value=!contextPicking.value}
function openContext(event){
  if(replaying.value || pinCommand.value || showSessionSettings.value)return
  clearPending()
  contextPicking.value=false
  const bounds=consoleRoot.value.getBoundingClientRect()
  contextMenu.value={...event,title:event.type==='point'?`${event.id} 号道岔 · ${event.section}`:event.type==='section'?event.id:event.type==='block'?`${event.id} 闭塞`:event.type==='signal'?`${event.id} 信号机`:'仿真会话',x:event.clientX-bounds.left,y:event.clientY-bounds.top,width:Math.min(bounds.width,window.innerWidth-bounds.left),height:Math.min(bounds.height,window.innerHeight-bounds.top),minX:Math.max(6,6-bounds.left),minY:Math.max(6,6-bounds.top),rootTop:bounds.top,rootLeft:bounds.left,key:Date.now()}
}
async function chooseContext(item){closeContext();if(item.action==='session'){confirmNew.value=false;showSessionSettings.value=true;return}if(item.action==='clear'){await runCommand((id,version)=>clearStationSelection(id,version));return}await inject(item.type,item.target,item.payload)}
function outsideContext(event){if(!event.target.closest('.console-context-menu'))closeContext()}
function scrollContext(event){
  if(!contextMenu.value || event.target?.closest?.('.console-context-menu'))return
  // A focus/scroll-into-view event queued before this menu opened is harmless.
  const bounds=consoleRoot.value.getBoundingClientRect()
  if(event.target===document && bounds.top===contextMenu.value.rootTop && bounds.left===contextMenu.value.rootLeft)return
  closeContext()
}
function clearPending(){pending.value=null;pin.value=''}
async function refresh(){if(!snapshot.value || busy.value || replaying.value)return;const id=snapshot.value.session_id;try{const result=await getSimulationSnapshot(id);if(!busy.value && snapshot.value?.session_id===id && result.version>=snapshot.value.version)snapshot.value=result;stale.value=false}catch{stale.value=true}}
async function boot(){
  loading.value=true;loadError.value='';snapshot.value=null
  try{station.value=await getStationPackage('reference');if(client.loadSession){snapshot.value=await client.loadSession()}else{const prior=sessionStorage.getItem(storageKey.value);if(prior){try{snapshot.value=await getSimulationSnapshot(prior)}catch{sessionStorage.removeItem(storageKey.value)}}if(!snapshot.value)await startNewSession()}intervalAvailable.value=snapshot.value.interval_available;stale.value=false;const p=snapshot.value.pending;if(p){const command=visibleCommands.value.find(c=>c.type===p.type);if(command){if(command.sealed){pinCommand.value=command;await nextTick();pinInput.value?.focus()}else pending.value={...command,deadline:p.expires_at*1000}}}}
  catch{loadError.value='站场加载失败，请确认后端已启动并重新登录。';stale.value=true}finally{loading.value=false}
}
async function startNewSession(){snapshot.value=await createSimulationSession(intervalAvailable.value,[],'reference');sessionStorage.setItem(storageKey.value,snapshot.value.session_id);acknowledged.value=0;confirmNew.value=false;stale.value=false}
async function newSession(){if(!confirmNew.value){confirmNew.value=true;return}busy.value=true;try{clearPending();await startNewSession();showSessionSettings.value=false}finally{busy.value=false}}
function runCommand(action){if(props.readOnly)return Promise.resolve();commandQueue=commandQueue.then(async()=>{if(disposed || !snapshot.value || replaying.value || stale.value)return;busy.value=true;try{snapshot.value=await getSimulationSnapshot(snapshot.value.session_id);const response=await action(snapshot.value.session_id,snapshot.value.version);if(disposed)return;snapshot.value=response.snapshot;if(!response.accepted)ElMessage.warning(response.message);return response}catch{try{snapshot.value=await getSimulationSnapshot(snapshot.value.session_id);ElMessage.warning('操作未完成，已刷新状态，请重新选择')}catch{stale.value=true}}finally{busy.value=false}});return commandQueue}
async function pressButton(button){if(pending.value){const signal=station.value.buttons.find(b=>b.name===button)?.signal;if(signal)await selectSignal(signal);return}await runCommand((id,version)=>pressStationButton(id,button,version))}
async function pressGuide(name){if(displaySnapshot.value?.signals?.[name]?.aspect==='HB'){await inject('GUIDE_MAINTAIN',name);return}await chooseCommand({label:`${name} 引导`,type:'GUIDE_ARM',sealed:true,fixedTarget:name})}
async function chooseCommand(command){if(props.readOnly || command.unavailable || replaying.value)return;contextPicking.value=false;clearPending();if(command.type==='CLEAR_SELECTION'){await runCommand((id,version)=>clearStationSelection(id,version));return}if(client.selectFunction){const reply=await runCommand(()=>client.selectFunction(command));if(!reply?.accepted)return}if(command.sealed){pinCommand.value=command;await nextTick();pinInput.value?.focus()}else{pending.value={...command,deadline:Date.now()+15000};if(command.fixedTarget)await executeTarget(command.fixedTarget)}}
function confirmPin(){if(!pin.value){notify('请输入教学操作口令');return}const target=pinCommand.value.fixedTarget;pending.value={...pinCommand.value,pin:pin.value,deadline:Date.now()+15000};pin.value='';pinCommand.value=null;if(target)executeTarget(target)}
function cancelPin(){if(pinCommand.value && client.cancelFunction)runCommand(()=>client.cancelFunction());pinCommand.value=null;pin.value='';clearPending()}
async function executeTarget(target,payload={}){const command=pending.value;if(!command)return;if(command.deadline<=Date.now()){clearPending();return}clearPending();await runCommand((id,version)=>operateConsole(id,{type:command.type,target,pin:command.pin,payload},version))}
async function selectGroup(id){if(pending.value?.target==='switch')await executeTarget(id);else if(pending.value?.target==='section'){const point=station.value.switches.find(p=>p.id===id);if(point)await executeTarget(point.section)}else if(pending.value)notify(`请点击${targetLabel(pending.value.target)}`)}
async function selectSignal(name){if(!pending.value)return;if(pending.value.target==='signal'){await executeTarget(name);return}if(pending.value.target==='route'){const route=activeRoutes.value.find(r=>r.signal===name || r.segment_signals?.includes(name));if(route)await executeTarget(route.id,{signal:name});else if(pending.value.type==='MANUAL_UNLOCK_ROUTE' && displaySnapshot.value?.signals?.[name]?.aspect==='HB')await executeTarget(name);else notify(`${name} 没有仍锁闭的原进路`)}else notify(`请点击${targetLabel(pending.value.target)}`)}
function inspectDevice(type,name){if(type==='区段' && pending.value?.target==='section')executeTarget(name)}
async function inject(type,target,payload={}){await runCommand((id,version)=>operateConsole(id,{type,target,payload},version))}
function acknowledgeAlarms(){acknowledged.value=displaySnapshot.value?.version || 0}
async function openReplay(){if(!snapshot.value || busy.value)return;contextPicking.value=false;clearPending();closeContext();try{replayFrames.value=await getSimulationReplay(snapshot.value.session_id);if(replayFrames.value.length){replayIndex.value=replayFrames.value.length-1;replaying.value=true}}catch{ElMessage.warning('读取回放失败')}}
function closeReplay(){replaying.value=false;refresh()}
function onKey(event){if(event.key==='Escape'){if(pending.value && !pinCommand.value && client.cancelFunction)runCommand(()=>client.cancelFunction());contextPicking.value=false;clearPending();cancelPin();closeContext();showSessionSettings.value=false}}
onMounted(async()=>{document.addEventListener('keydown',onKey);document.addEventListener('pointerdown',outsideContext);window.addEventListener('resize',closeContext);document.addEventListener('scroll',scrollContext,true);await boot();poller=window.setInterval(()=>{const t=Date.now();if(t-lastPoll>=250){lastPoll=t;refresh()}},250);ticker=window.setInterval(()=>{now.value=Date.now();if(pending.value && pending.value.deadline<=now.value)clearPending()},250)})
onBeforeUnmount(()=>{disposed=true;document.removeEventListener('keydown',onKey);document.removeEventListener('pointerdown',outsideContext);window.removeEventListener('resize',closeContext);document.removeEventListener('scroll',scrollContext,true);clearInterval(poller);clearInterval(ticker)})
defineExpose({sync:data=>{snapshot.value=data},flush:async()=>{await commandQueue;return snapshot.value},busy})
</script>

<style scoped>
.console-menu button.menu-picking{background:#ffff00;box-shadow:inset 0 0 0 1px #808080}.console-menu button:disabled{color:#696969;cursor:default}
.simulation-page{display:grid;gap:16px}.page-intro{display:flex;align-items:center;justify-content:space-between;gap:20px}.page-intro h1{font-size:26px;margin:4px 0 10px;color:#183b60}.page-intro p{margin:0;color:#627386;font-size:14px;line-height:1.7}.page-intro .eyebrow{font-size:10px;letter-spacing:2px;color:#006fab}.source-picker{display:grid;gap:7px;font-size:13px;white-space:nowrap}.source-picker select{padding:8px;border:1px solid #bcc6ce;background:white;border-radius:4px;color:#23415e}
.console-shell{position:relative;display:flex;flex-direction:column;height:800px;min-height:650px;overflow:hidden;background:#000;border:2px solid #808080;font-family:SimHei,'Microsoft YaHei',sans-serif;color:#c0c0c0}.console-shell:fullscreen{width:100vw;height:100vh;min-height:0;border:0}.console-menu{display:flex;align-items:center;background:#c0c0c0;color:black;border-bottom:2px solid #808080;min-height:36px;padding:0 8px;font-size:14px}.console-menu strong{margin-right:15px}.mode-label{color:#424242;font-size:12px;margin-right:14px}.console-menu button{border:0;background:none;color:black;padding:8px 12px;font-size:14px;cursor:pointer}.console-menu button:hover{background:#efefef}.console-menu .fullscreen-button{margin-left:auto}.console-body{display:flex;flex:1;min-height:0;background:black;overflow:hidden}.stage-wrap{position:relative;flex:1;overflow:auto;min-width:0;background:black}
.alarm-region{position:absolute;z-index:2;left:6px;top:6px;width:min(335px,30%);height:94px;overflow:auto;background:#808080;color:black;font:14px SimHei,sans-serif;border:1px solid #c0c0c0}.alarm-region.alarming{background:#ff0000}.alarm-region header{position:sticky;top:0;display:flex;align-items:center;justify-content:space-between;background:inherit;padding:2px 6px;font-size:12px}.alarm-region header button{padding:1px 4px;background:#c0c0c0;color:black;border:1px solid #333;font-size:12px}.alarm-line{padding:1px 5px;line-height:1.25}.no-alarm{padding:10px}.equipment-region{position:absolute;top:6px;right:6px;z-index:2;display:flex;gap:4px;background:#808080;padding:6px;border:1px solid silver;color:black;font-size:14px}.equipment-region div{display:grid;text-align:center;gap:4px}.equipment-region span{padding:0 8px}.equipment-region b{display:block;padding:5px;background:#00ff00;color:black;font-weight:400}.equipment-region b.failed{background:red}
.function-region{display:grid;grid-template-columns:repeat(15,minmax(0,1fr));background:#c0c0c0;flex-shrink:0;border-top:2px solid #808080;overflow-x:auto}.function-button{min-width:64px;min-height:56px;background:#efefef;border:2px outset #ddd;color:black;font:16px SimHei,'Microsoft YaHei',sans-serif;display:flex;align-items:center;justify-content:center;gap:3px;cursor:pointer;white-space:nowrap;padding:3px}.function-button img{width:15px;height:15px;image-rendering:pixelated}.function-button.sealed{color:red}.function-button.pressed{background:#ffff00;border-style:inset}.function-button:disabled{color:#696969;cursor:not-allowed}.function-button:hover:not(:disabled){outline:1px solid black;outline-offset:-4px}.hint-region{display:flex;align-items:center;justify-content:space-between;gap:10px;background:#808080;color:black;min-height:31px;font-size:16px;padding:3px 8px;flex-shrink:0}.hint-region span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.hint-region time{white-space:nowrap;border-left:1px solid #444;padding-left:10px;font-size:14px}
.help-panel{position:absolute;z-index:4;top:114px;right:16px;width:min(430px,80%);padding:18px;background:#efefef;color:black;border:2px outset #c0c0c0;box-shadow:0 6px 24px #0008;font-size:14px;line-height:1.6}.help-panel>button{float:right;border:0;background:transparent;font-size:20px}.help-panel p{margin:9px 0}.pin-backdrop{position:absolute;inset:0;display:grid;place-items:center;z-index:10;background:#0005}.pin-dialog{display:grid;gap:12px;width:330px;padding:24px;background:#c0c0c0;color:black;border:3px outset #eee;font-size:16px;box-shadow:0 12px 40px #0008}.pin-dialog p{font-size:14px;margin:0}.pin-dialog input{padding:10px;border:2px inset #ddd;background:white;color:black;font-size:20px}.pin-dialog small{font-size:12px;line-height:1.5}.pin-dialog div{display:flex;gap:10px;justify-content:flex-end}.pin-dialog button{padding:7px 20px;background:#efefef;border:2px outset #ddd;color:black}.load-error{padding:15px;background:#f9e5e5;color:#900}.load-error button{margin-left:15px}.replay-bar{display:flex;align-items:center;gap:16px;padding:8px;background:#ffff00;color:black;font-size:14px}.replay-bar input{flex:1}
.device-workbench,.activity-panel,.route-audit{padding:18px;border:1px solid #cbd3da;border-radius:5px;background:white;color:#30465a;font-size:14px}.device-workbench>div,.activity-heading{display:flex;align-items:center;gap:15px}.device-workbench span,.activity-heading span{color:#6b7d8d;font-size:12px}.device-workbench button,.device-workbench select,.route-card button{padding:6px 10px;margin:0 8px 8px 0;border:1px solid #b3c0cc;border-radius:3px;background:#f5f7fa;color:#23415e}.device-workbench label{display:inline-flex;align-items:center;gap:7px;margin-right:10px}.device-workbench p{line-height:1.6}.route-cards{display:flex;flex-wrap:wrap;gap:12px}.route-card{display:grid;gap:8px;border:1px solid #d2dbe4;padding:12px;min-width:210px}.route-card strong{font-weight:500}.route-card button:disabled{opacity:.5;cursor:not-allowed}.activity-heading{margin-bottom:12px}.empty-route{color:#6b7d8d;margin-bottom:0}.route-audit label{display:flex;gap:10px;align-items:center;margin-bottom:12px}.route-audit input{padding:6px 9px;border:1px solid #c3ccd4}.audit-scroll{max-height:320px;overflow:auto}.route-audit table{border-collapse:collapse;width:100%;text-align:left;font-size:13px}.route-audit th,.route-audit td{padding:9px;border-bottom:1px solid #e1e7ec}.route-audit th{position:sticky;top:0;background:#eff3f6}.audit-blocked{color:#ab6117}.under-note{font-size:12px;line-height:1.7;color:#6b7d8d;margin:0}
.device-workbench,.activity-panel,.route-audit{position:absolute;z-index:5;right:14px;top:125px;width:min(520px,calc(100% - 28px));max-height:calc(100% - 240px);overflow:auto;box-sizing:border-box;box-shadow:0 8px 28px #0008}.activity-heading{flex-wrap:wrap}
@media(max-width:1100px){.function-region{display:flex}.function-button{flex:0 0 85px}.console-menu .mode-label{display:none}.console-menu button{padding:8px}.page-intro{align-items:flex-start}.activity-heading{align-items:flex-start;flex-direction:column;gap:6px}.console-shell{height:780px}}
.console-shell:fullscreen,.console-shell.window-fullscreen{height:100dvh;min-height:0;max-width:none;width:100%}.stage-wrap :deep(.reference-diagram){min-width:0;min-height:0}.console-menu{flex-wrap:wrap;flex-shrink:0}.function-region{display:flex;flex-wrap:wrap;padding:3px;gap:2px}.function-button{flex:1 0 80px;font:500 14px 'Microsoft YaHei',SimHei,sans-serif;letter-spacing:.5px;min-height:42px;padding:6px 10px;background:#dedede;border:2px outset #f3f3f3}.function-button.pressed{background:#ffff00;border-style:inset}
.console-shell .function-region{display:grid;grid-template-columns:repeat(15,minmax(0,1fr));overflow:visible}.function-region .function-button{min-width:0;padding:6px}
@container(max-width:1200px){.console-shell .function-region{grid-template-columns:repeat(8,minmax(0,1fr))}}
@container(max-width:800px){.console-shell .function-region{grid-template-columns:repeat(5,minmax(0,1fr))}}
</style>
