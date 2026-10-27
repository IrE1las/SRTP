<template>
  <div class="simulation-page">
    <div class="page-intro">
      <div><p class="eyebrow">COMPUTER BASED INTERLOCKING</p><h2>联锁仿真操作台</h2>
        <p>选择始端与终端办理进路；先按功能按钮，再选择对应设备。红色提示说明操作未通过的原因。</p></div>
    </div>
    <div ref="consoleRoot" class="console-shell" v-loading="loading">
      <nav class="console-menu" aria-label="操作台菜单">
        <strong>{{ station?.station_name || '联锁仿真' }}</strong><span class="mode-label">教学仿真</span>
        <button @click="showRoutes = !showRoutes; showDevices=false; showActivity=false">进路与核对</button><button @click="showDevices = !showDevices; showRoutes=false; showActivity=false">设备练习</button>
        <button @click="showActivity = !showActivity; showDevices=false; showRoutes=false">活动进路 {{ activeRoutes.length }}</button>
        <button @click="replaying ? closeReplay() : openReplay()">{{ replaying ? '返回实时' : '操作回放' }}</button>
        <button @click="showHelp = !showHelp">操作说明</button><button class="fullscreen-button" @click="toggleFullscreen">{{ isFullscreen ? '退出全屏' : '全屏站场' }}</button>
      </nav>
      <div v-if="loadError" class="load-error" role="alert">{{ loadError }}<button @click="boot">重试加载</button></div>
      <div v-if="replaying" class="replay-bar"><strong>只读回放</strong><input v-model.number="replayIndex" type="range" min="0" :max="Math.max(0,replayFrames.length-1)" aria-label="回放时间轴" /><span>{{ replayIndex+1 }} / {{ replayFrames.length }}</span><button @click="closeReplay">结束回放</button></div>
      <div class="console-body"><div v-if="station" class="stage-wrap">
        <ReferenceStationDiagram v-if="source === 'reference'" :station="station" :snapshot="displaySnapshot" :selected="displaySnapshot?.selected_buttons || []" :targeting="pending?.target"
          @press="pressButton" @inspect="inspectDevice" @group="selectGroup" @signal="selectSignal" @block="chooseCommand" />
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
          <p>空闲浅蓝，锁闭白色，占用红色；定位绿色，反位黄色，失表示红闪。</p>
          <p v-if="source === 'reference'">本站独立使用原软件 {{ station.counts.candidate_routes }} 条进路定义。通过按钮以 TA 标识；同按钮多路径按可用条件选排。引导须先将道岔就位，选择进站始端和接车终端，并每 15 秒内办理引导保持。</p>
          <p v-if="source === 'reference'">区故解先确认区段恢复空闲，再按功能、输入口令、点击区段。区间请求后，可在本题设备练习中模拟邻站同意。</p>
        </div>
      </div></div>
      <div class="function-region" aria-label="常用功能按钮区">
        <button v-for="command in visibleCommands" :key="command.label" class="function-button" :class="{ sealed: command.sealed, pressed: pending?.type === command.type && !command.unavailable }"
          :disabled="busy || replaying || stale || !!command.unavailable" :title="command.unavailable || command.label" :aria-pressed="pending?.type === command.type && !command.unavailable" @click="chooseCommand(command)">
          <img :src="`/simulator-reference/menubitmap/${command.icon}.png`" alt="" />{{ command.label }}
        </button>
      </div>
      <div class="hint-region" aria-label="提示信息区" aria-live="polite"><span>{{ pending ? `${pending.label}：请选择${targetLabel(pending.target)}（${pendingRemaining}秒）` : displaySnapshot?.selected_buttons?.length ? `已选 ${displaySnapshot.selected_buttons.join(' → ')}，等待下一按钮（${displaySnapshot.selection_remaining_seconds}秒）` : displaySnapshot?.last_message || '等待操作' }}</span><time aria-label="时钟信息区">{{ clockText }}</time></div>
      <div v-if="pinCommand" class="pin-backdrop" @keydown.esc="cancelPin"><form class="pin-dialog" role="dialog" aria-modal="true" aria-labelledby="pin-title" @submit.prevent="confirmPin">
        <strong id="pin-title">{{ pinCommand.label }} · 口令确认</strong><p>请输入教学操作口令，然后选择目标设备。</p><input ref="pinInput" v-model="pin" type="password" maxlength="32" autocomplete="off" aria-label="教学操作口令" />
        <small>默认教学口令为 0000；可由管理员通过服务器配置修改。</small><div><button type="button" @click="cancelPin">取消</button><button type="submit">确认</button></div>
      </form></div>
    <div v-if="showDevices && station" class="device-workbench">
      <div><strong>设备练习</strong><span>先选择设备，在本题独立操作台观察故障、占用和恢复。</span></div><p>{{ inspected ? `${inspected.type} ${inspected.name}：${inspectedState}` : '尚未选择设备' }}</p>
      <template v-if="inspected?.type === '道岔' && canControlTrain"><button @click="inject('SET_SWITCH_INDICATION', inspected.name)">{{ '本端失表示' }}</button><button @click="inject('RESTORE_SWITCH_INDICATION', inspected.name)">{{ '恢复本端表示' }}</button></template>
      <template v-if="inspected?.type === '区段' && canControlTrain"><button @click="inject('SET_SECTION_OCCUPANCY', inspected.name, { kind:'vehicle' })">车列占用</button><button @click="inject('SET_SECTION_OCCUPANCY', inspected.name, { kind:'fault' })">故障占用</button><button @click="inject('CLEAR_SECTION_OCCUPANCY', inspected.name)">恢复空闲</button></template>
      <div v-if="source === 'reference'"><p>闭塞采用本地邻站模拟，设备状态与各区间分别保存。</p></div>
      <div v-for="block in source === 'reference' ? Object.values(displaySnapshot?.blocks || {}) : []" :key="block.signal">
        <span>{{ block.signal }} · {{ block.phase === 'permitted' ? '已许可' : block.phase === 'idle' ? '未闭塞' : '等待邻站' }}</span>
        <button v-if="canControlTrain" :disabled="!['requested','awaiting_peer'].includes(block.phase)" @click="inject('BLOCK_PEER_ACCEPT', block.signal)">模拟邻站同意</button>
      </div>
      <label>新会话区间许可<select v-model="intervalAvailable"><option :value="true">已具备</option><option :value="false">未具备（条件反例）</option></select></label><button @click="newSession" :disabled="busy || replaying">{{ confirmNew ? '确认重新初始化' : '重新初始化操作台' }}</button>
    </div>
    <section class="activity-panel" v-if="station && showActivity"><div class="activity-heading"><strong>活动进路</strong><span>推进本题模拟车辆，观察占用、信号关闭及正常解锁。</span></div>
      <p v-if="!activeRoutes.length" class="empty-route">暂无活动进路。{{ '调车示例：D3 → D7。' }}</p>
      <div class="route-cards"><div v-for="route in activeRoutes" :key="route.id" class="route-card"><strong>{{ routeName(route.route_id) }}</strong><span>{{ statusText(route) }}</span><button :disabled="busy || replaying || stale || !canControlTrain || ['setting','track_proving','cancelling','clearing','manual_unlocking','closed_locked'].includes(route.status)" @click="advance(route.id)">仿真行车 · 推进一步</button></div></div>
    </section>
    <section v-if="showRoutes && station" class="route-audit"><div class="activity-heading"><strong>{{ '原软件进路与来源' }}</strong><span>可解析办理 {{ station.counts.ready_routes }} · 数据异常 {{ station.counts.blocked_routes }} · 共 {{ station.counts.candidate_routes }}</span></div>
      <p v-if="!station.routes">学生可在站场自由操作；完整进路条件和核对清单由教师查看。</p>
      <template v-else><label>查找进路<input v-model="routeQuery" placeholder="如 XD、D3、S5" /></label><div class="audit-scroll"><table><thead><tr><th>进路</th><th>按钮顺序</th><th>状态 / 来源</th></tr></thead><tbody><tr v-for="route in filteredRoutes" :key="route.id"><td>{{ route.name || route.id }}</td><td>{{ route.button_sequence.join(' → ') }}</td><td :class="{ 'audit-blocked':route.status!=='ready' }">{{ route.status === 'ready' ? '可办理' : route.reasons.join('；') }}<template v-if="source === 'reference'"> · 原文件第 {{ route.source_row }} 行<span v-for="warning in route.warnings" :key="warning">；{{ warning }}</span></template></td></tr></tbody></table></div></template>
    </section>
    </div>
    <p class="under-note">本题使用独立联锁仿真操作台。模拟操作不会代填或提交答题栏；操作台重启后重新初始化，已提交的理论作答保留。</p>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/store/user'
import ReferenceStationDiagram from './ReferenceStationDiagram.vue'
import { COMMANDS } from './standardDisplay'
import { createTheoryConsoleClient } from '@/api/theoryConsole'
const props=defineProps({questionKey:{type:String,required:true}})
const { advanceSimulationTrain,clearStationSelection,createSimulationSession,getSimulationReplay,getSimulationSnapshot,getStationPackage,operateConsole,pressStationButton }=createTheoryConsoleClient(props.questionKey)
const userStore=useUserStore(), consoleRoot=ref(null), source=ref('reference'), station=ref(null), snapshot=ref(null)
const loading=ref(true), busy=ref(false), stale=ref(false), loadError=ref(''), isFullscreen=ref(false)
const showRoutes=ref(false), showDevices=ref(false), showActivity=ref(false), showHelp=ref(false), inspected=ref(null), intervalAvailable=ref(true), confirmNew=ref(false)
const replaying=ref(false), replayFrames=ref([]), replayIndex=ref(0), acknowledged=ref(0), routeQuery=ref('')
const pending=ref(null), pinCommand=ref(null), pin=ref(''), pinInput=ref(null), now=ref(Date.now())
let poller, ticker, lastPoll=0, disposed=false
let commandQueue=Promise.resolve()
const storageKey=computed(()=>props.questionKey+'-'+`srtp-console-${source.value}-${userStore.user?.id || 'anonymous'}`)
const canControlTrain=computed(()=>true)
const visibleCommands=computed(()=>COMMANDS.filter(c=>!c.referenceOnly || source.value==='reference'))
const displaySnapshot=computed(()=>replaying.value ? replayFrames.value[replayIndex.value] : snapshot.value)
const activeRoutes=computed(()=>(displaySnapshot.value?.routes || []).filter(r=>!['released','cancelled'].includes(r.status)))
const alarms=computed(()=>(displaySnapshot.value?.events || []).filter(e=>e.version>acknowledged.value && (e.kind==='rejected' || ['SET_SWITCH_INDICATION','signal_close','switch_timeout','route_setting_failed'].includes(e.kind))).slice(-8).reverse())
const faultCount=computed(()=>Object.values(displaySnapshot.value?.switches || {}).filter(s=>s.represented===false && !s.moving).length+Object.values(displaySnapshot.value?.sections || {}).filter(s=>s.occupancy_kind==='fault').length)
const clockText=computed(()=>new Date(now.value).toLocaleString('zh-CN',{hour12:false,timeZone:'Asia/Shanghai'}))
const pendingRemaining=computed(()=>Math.max(0,Math.ceil(((pending.value?.deadline || 0)-now.value)/1000)))
const filteredRoutes=computed(()=>(station.value?.routes || []).filter(r=>`${r.name || r.id} ${r.button_sequence.join(' ')}`.toLowerCase().includes(routeQuery.value.toLowerCase())))
const inspectedState=computed(()=>{
  if(!inspected.value)return ''
  const {type,name}=inspected.value,s=displaySnapshot.value
  if(type==='道岔'){const p=s?.switches?.[name];return `${p?.moving ? `向${p.target_position?'反位':'定位'}转换，等待本端表示` : `${p?.position?'反位':'定位'}，${p?.represented===false ? p.movement_failed?'转换超时，失表示':'失表示' : '表示正常'}`}${p?.locked?'，进路锁闭':''}${p?.manual_locked?'，单锁':''}${p?.sealed?'，封锁':''}`}
  if(type==='区段'){const p=s?.sections?.[name];return p?.occupied ? p.occupancy_kind==='fault'?'故障占用':'车列占用' : p?.locked?'锁闭':'空闲'}
  return inspected.value.state
})
const notify=message=>ElMessage.info(message)
const eventTime=value=>new Date(value).toLocaleTimeString('zh-CN',{hour12:false,timeZone:'Asia/Shanghai'})
const targetLabel=target=>({switch:'道岔编号',signal:'信号机',route:'原进路始端信号',section:'轨道区段'})[target] || '设备'
const routeName=id=>station.value?.routes?.find(r=>r.id===id)?.name || id
function statusText(route){if(route.status==='cancelling')return '取消中，等待道岔、轨道光带及信号依次更新';if(route.cancelled_segments?.length)return `已取消 ${route.cancelled_segments.length} 个基本段，其余保持锁闭`;if(route.mode==='guide' && route.guide_remaining_seconds)return `引导开放，保持剩余 ${route.guide_remaining_seconds} 秒`;return route.status==='manual_unlocking' ? `人工解锁剩余 ${route.manual_remaining_seconds} 秒` : ({setting:'道岔转换中，等待各端到位表示',track_proving:'轨道光带已亮，等待信号开放',cancelling:'取消中，等待道岔、轨道光带及信号依次更新',signal_open:'信号开放',approaching:'车辆接近',clearing:'出清，等待正常解锁',closed_locked:'信号关闭，保持锁闭'})[route.status] || '车辆运行'}
function onFullscreenChange(){isFullscreen.value=document.fullscreenElement===consoleRoot.value}
async function toggleFullscreen(){try{if(isFullscreen.value)await document.exitFullscreen();else await consoleRoot.value?.requestFullscreen()}catch{notify('浏览器未允许全屏，可继续在当前窗口操作')}}
function clearPending(){pending.value=null;pin.value=''}
async function refresh(){if(!snapshot.value || busy.value || replaying.value)return;const id=snapshot.value.session_id;try{const result=await getSimulationSnapshot(id);if(!busy.value && snapshot.value?.session_id===id && result.version>=snapshot.value.version)snapshot.value=result;stale.value=false}catch{stale.value=true}}
async function boot(){
  loading.value=true;loadError.value='';snapshot.value=null
  try{station.value=await getStationPackage(source.value);const prior=sessionStorage.getItem(storageKey.value);if(prior){try{snapshot.value=await getSimulationSnapshot(prior)}catch(e){if(![404,409].includes(e.response?.status))throw e;sessionStorage.removeItem(storageKey.value)}}if(!snapshot.value)await startNewSession();intervalAvailable.value=snapshot.value.interval_available;stale.value=false}
  catch{loadError.value='站场加载失败，请确认后端已启动并重新登录。';stale.value=true}finally{loading.value=false}
}
async function startNewSession(){snapshot.value=await createSimulationSession(intervalAvailable.value,[],source.value);sessionStorage.setItem(storageKey.value,snapshot.value.session_id);acknowledged.value=0;confirmNew.value=false;stale.value=false}
async function newSession(){if(!confirmNew.value){confirmNew.value=true;notify('再点一次清空本题模拟状态；答题草稿保留');return}busy.value=true;try{clearPending();await startNewSession()}finally{busy.value=false}}
function runCommand(action){commandQueue=commandQueue.then(async()=>{if(disposed || !snapshot.value || replaying.value || stale.value)return;busy.value=true;try{const response=await action(snapshot.value.session_id,snapshot.value.version);snapshot.value=response.snapshot;if(!response.accepted)ElMessage.warning(response.message)}catch{try{snapshot.value=await getSimulationSnapshot(snapshot.value.session_id);ElMessage.warning('操作未完成，已刷新状态，请重新选择')}catch{stale.value=true}}finally{busy.value=false}});return commandQueue}
async function pressButton(button){if(pending.value){const signal=station.value.buttons.find(b=>b.name===button)?.signal;if(signal)await selectSignal(signal);return}await runCommand((id,version)=>pressStationButton(id,button,version))}
async function chooseCommand(command){if(command.unavailable || replaying.value)return;clearPending();if(command.type==='CLEAR_SELECTION'){await runCommand((id,version)=>clearStationSelection(id,version));return}if(command.sealed){pinCommand.value=command;await nextTick();pinInput.value?.focus()}else{pending.value={...command,deadline:Date.now()+15000};if(command.fixedTarget)await executeTarget(command.fixedTarget)}}
function confirmPin(){if(!pin.value){notify('请输入教学操作口令');return}const target=pinCommand.value.fixedTarget;pending.value={...pinCommand.value,pin:pin.value,deadline:Date.now()+15000};pin.value='';pinCommand.value=null;if(target)executeTarget(target)}
function cancelPin(){pinCommand.value=null;pin.value='';clearPending()}
async function executeTarget(target,payload={}){const command=pending.value;if(!command)return;if(command.deadline<=Date.now()){clearPending();return}clearPending();await runCommand((id,version)=>operateConsole(id,{type:command.type,target,pin:command.pin,payload},version))}
async function selectGroup(id){if(pending.value?.target==='switch')await executeTarget(id);else if(pending.value)notify(`请点击${targetLabel(pending.value.target)}`)}
async function selectSignal(name){if(!pending.value)return;if(pending.value.target==='signal'){await executeTarget(name);return}if(pending.value.target==='route'){const route=activeRoutes.value.find(r=>r.signal===name || r.segment_signals?.includes(name));if(route)await executeTarget(route.id,{signal:name});else notify(`${name} 没有仍锁闭的原进路`)}else notify(`请点击${targetLabel(pending.value.target)}`)}
function inspectDevice(type,name,state){inspected.value={type,name,state};if(type==='区段' && pending.value?.target==='section'){executeTarget(name);return}}
async function inject(type,target,payload={}){await runCommand((id,version)=>operateConsole(id,{type,target,payload},version))}
async function advance(instance){await runCommand((id,version)=>advanceSimulationTrain(id,instance,version))}
function acknowledgeAlarms(){acknowledged.value=displaySnapshot.value?.version || 0}
async function openReplay(){if(!snapshot.value || busy.value)return;clearPending();try{replayFrames.value=await getSimulationReplay(snapshot.value.session_id);if(replayFrames.value.length){replayIndex.value=replayFrames.value.length-1;replaying.value=true}}catch{ElMessage.warning('读取回放失败')}}
function closeReplay(){replaying.value=false;refresh()}
function onKey(event){if(event.key==='Escape'){clearPending();cancelPin()}}
onMounted(async()=>{document.addEventListener('fullscreenchange',onFullscreenChange);document.addEventListener('keydown',onKey);await boot();if(disposed)return;poller=window.setInterval(()=>{const t=Date.now();if(source.value==='reference' || t-lastPoll>=1000){lastPoll=t;refresh()}},250);ticker=window.setInterval(()=>{now.value=Date.now();if(pending.value && pending.value.deadline<=now.value)clearPending()},250)})
onBeforeUnmount(()=>{disposed=true;document.removeEventListener('fullscreenchange',onFullscreenChange);document.removeEventListener('keydown',onKey);clearInterval(poller);clearInterval(ticker)})
</script>

<style scoped>
.simulation-page{display:grid;gap:16px}.page-intro{display:flex;align-items:center;justify-content:space-between;gap:20px}.page-intro h2{font-size:26px;margin:4px 0 10px;color:#183b60}.page-intro p{margin:0;color:#627386;font-size:14px;line-height:1.7}.page-intro .eyebrow{font-size:10px;letter-spacing:2px;color:#006fab}.source-picker{display:grid;gap:7px;font-size:13px;white-space:nowrap}.source-picker select{padding:8px;border:1px solid #bcc6ce;background:white;border-radius:4px;color:#23415e}
.console-shell{position:relative;display:flex;flex-direction:column;height:800px;min-height:650px;overflow:hidden;background:#000;border:2px solid #808080;font-family:SimHei,'Microsoft YaHei',sans-serif;color:#c0c0c0}.console-shell:fullscreen{width:100vw;height:100vh;min-height:0;border:0}.console-menu{display:flex;align-items:center;background:#c0c0c0;color:black;border-bottom:2px solid #808080;min-height:36px;padding:0 8px;font-size:14px}.console-menu strong{margin-right:15px}.mode-label{color:#424242;font-size:12px;margin-right:14px}.console-menu button{border:0;background:none;color:black;padding:8px 12px;font-size:14px;cursor:pointer}.console-menu button:hover{background:#efefef}.console-menu .fullscreen-button{margin-left:auto}.console-body{display:flex;flex:1;min-height:0;background:black;overflow:hidden}.stage-wrap{position:relative;flex:1;overflow:auto;min-width:0;background:black}
.alarm-region{position:absolute;z-index:2;left:6px;top:6px;width:min(335px,30%);height:94px;overflow:auto;background:#808080;color:black;font:14px SimHei,sans-serif;border:1px solid #c0c0c0}.alarm-region.alarming{background:#ff0000}.alarm-region header{position:sticky;top:0;display:flex;align-items:center;justify-content:space-between;background:inherit;padding:2px 6px;font-size:12px}.alarm-region header button{padding:1px 4px;background:#c0c0c0;color:black;border:1px solid #333;font-size:12px}.alarm-line{padding:1px 5px;line-height:1.25}.no-alarm{padding:10px}.equipment-region{position:absolute;top:6px;right:6px;z-index:2;display:flex;gap:4px;background:#808080;padding:6px;border:1px solid silver;color:black;font-size:14px}.equipment-region div{display:grid;text-align:center;gap:4px}.equipment-region span{padding:0 8px}.equipment-region b{display:block;padding:5px;background:#00ff00;color:black;font-weight:400}.equipment-region b.failed{background:red}
.function-region{display:grid;grid-template-columns:repeat(15,minmax(0,1fr));background:#c0c0c0;flex-shrink:0;border-top:2px solid #808080;overflow-x:auto}.function-button{min-width:64px;min-height:56px;background:#efefef;border:2px outset #ddd;color:black;font:16px SimHei,'Microsoft YaHei',sans-serif;display:flex;align-items:center;justify-content:center;gap:3px;cursor:pointer;white-space:nowrap;padding:3px}.function-button img{width:15px;height:15px;image-rendering:pixelated}.function-button.sealed{color:red}.function-button.pressed{background:#ffff00;border-style:inset}.function-button:disabled{color:#696969;cursor:not-allowed}.function-button:hover:not(:disabled){outline:1px solid black;outline-offset:-4px}.hint-region{display:flex;align-items:center;justify-content:space-between;gap:10px;background:#808080;color:black;min-height:31px;font-size:16px;padding:3px 8px;flex-shrink:0}.hint-region span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.hint-region time{white-space:nowrap;border-left:1px solid #444;padding-left:10px;font-size:14px}
.help-panel{position:absolute;z-index:4;top:114px;right:16px;width:min(430px,80%);padding:18px;background:#efefef;color:black;border:2px outset #c0c0c0;box-shadow:0 6px 24px #0008;font-size:14px;line-height:1.6}.help-panel>button{float:right;border:0;background:transparent;font-size:20px}.help-panel p{margin:9px 0}.pin-backdrop{position:absolute;inset:0;display:grid;place-items:center;z-index:10;background:#0005}.pin-dialog{display:grid;gap:12px;width:330px;padding:24px;background:#c0c0c0;color:black;border:3px outset #eee;font-size:16px;box-shadow:0 12px 40px #0008}.pin-dialog p{font-size:14px;margin:0}.pin-dialog input{padding:10px;border:2px inset #ddd;background:white;color:black;font-size:20px}.pin-dialog small{font-size:12px;line-height:1.5}.pin-dialog div{display:flex;gap:10px;justify-content:flex-end}.pin-dialog button{padding:7px 20px;background:#efefef;border:2px outset #ddd;color:black}.load-error{padding:15px;background:#f9e5e5;color:#900}.load-error button{margin-left:15px}.replay-bar{display:flex;align-items:center;gap:16px;padding:8px;background:#ffff00;color:black;font-size:14px}.replay-bar input{flex:1}
.device-workbench,.activity-panel,.route-audit{padding:18px;border:1px solid #cbd3da;border-radius:5px;background:white;color:#30465a;font-size:14px}.device-workbench>div,.activity-heading{display:flex;align-items:center;gap:15px}.device-workbench span,.activity-heading span{color:#6b7d8d;font-size:12px}.device-workbench button,.device-workbench select,.route-card button{padding:6px 10px;margin:0 8px 8px 0;border:1px solid #b3c0cc;border-radius:3px;background:#f5f7fa;color:#23415e}.device-workbench label{display:inline-flex;align-items:center;gap:7px;margin-right:10px}.device-workbench p{line-height:1.6}.route-cards{display:flex;flex-wrap:wrap;gap:12px}.route-card{display:grid;gap:8px;border:1px solid #d2dbe4;padding:12px;min-width:210px}.route-card strong{font-weight:500}.route-card button:disabled{opacity:.5;cursor:not-allowed}.activity-heading{margin-bottom:12px}.empty-route{color:#6b7d8d;margin-bottom:0}.route-audit label{display:flex;gap:10px;align-items:center;margin-bottom:12px}.route-audit input{padding:6px 9px;border:1px solid #c3ccd4}.audit-scroll{max-height:320px;overflow:auto}.route-audit table{border-collapse:collapse;width:100%;text-align:left;font-size:13px}.route-audit th,.route-audit td{padding:9px;border-bottom:1px solid #e1e7ec}.route-audit th{position:sticky;top:0;background:#eff3f6}.audit-blocked{color:#ab6117}.under-note{font-size:12px;line-height:1.7;color:#6b7d8d;margin:0}
.device-workbench,.activity-panel,.route-audit{position:absolute;z-index:5;right:14px;top:125px;width:min(520px,calc(100% - 28px));max-height:calc(100% - 240px);overflow:auto;box-sizing:border-box;box-shadow:0 8px 28px #0008}.activity-heading{flex-wrap:wrap}
@media(max-width:1100px){.function-region{display:flex}.function-button{flex:0 0 85px}.console-menu .mode-label{display:none}.console-menu button{padding:8px}.page-intro{align-items:flex-start}.activity-heading{align-items:flex-start;flex-direction:column;gap:6px}.console-shell{height:780px}}
</style>
