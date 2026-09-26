<template>
  <div class="simulation-page">
    <div class="page-intro">
      <div>
        <p class="eyebrow">STATION SIMULATION / 第一阶段</p>
        <h1>联锁仿真操作台</h1>
        <p>按本站按钮序列办理常规接车、发车与调车，观察道岔、区段和信号联动。进入全屏后开始操作。</p>
      </div>
      <el-tag type="info" effect="plain">独立教学仿真</el-tag>
    </div>

    <div ref="consoleRoot" class="console-shell" :class="{ 'is-fullscreen': isFullscreen }" v-loading="loading">
      <header class="console-header">
        <div class="console-brand"><span class="brand-mark">SRTP</span><div><strong>联锁测试站</strong><small>全站站场 · 数据版本 {{ station?.source_sha256?.slice(0, 8) || '载入中' }}</small></div></div>
        <div class="console-summary" v-if="station">
          <span>信号机 {{ station.counts.signals }}</span><span>道岔 {{ station.counts.switches }}</span>
          <span>区段 {{ station.counts.sections }}</span><span>按钮 {{ station.counts.buttons }}</span>
          <span class="status-ready">可办理 {{ station.counts.ready_routes }}</span>
          <span class="status-blocked">数据阻塞 {{ station.counts.blocked_routes }}</span>
        </div>
        <div class="console-header-actions">
          <button type="button" class="chrome-button" @click="showSwitches = !showSwitches">道岔表示</button>
          <button type="button" class="chrome-button" @click="showIssues = !showIssues">进路与问题</button>
          <button type="button" class="chrome-button" @click="replaying ? closeReplay() : openReplay()">{{ replaying ? '返回实时操作' : '事件回放' }}</button>
          <button type="button" class="chrome-button primary" @click="toggleFullscreen">{{ isFullscreen ? '退出全屏' : '进入全屏操作' }}</button>
        </div>
      </header>

      <div class="console-body">
        <div class="stage-wrap" v-if="station">
          <StationDiagram :station="station" :snapshot="displaySnapshot" :selected="displaySnapshot?.selected_buttons || []"
            @press="pressButton" @inspect="inspectDevice" @disabled="showDisabled" />
          <div v-if="showSwitches" class="switch-status-panel">
            <div class="switch-panel-head"><strong>道岔表示</strong><button type="button" @click="showSwitches = false" aria-label="收起道岔表示">×</button></div>
            <div class="switch-status-heading"><span>道岔</span><span>位置</span><span>状态</span></div>
            <div class="switch-status-list">
              <div v-for="point in station.switches" :key="point.id" class="switch-status-row">
                <span>{{ point.name }}</span>
                <span><i class="switch-lamp" :class="{ reverse: displaySnapshot?.switches?.[point.id]?.position === 1 }"></i>{{ displaySnapshot?.switches?.[point.id]?.position === 1 ? '反位' : '定位' }}</span>
                <span>{{ displaySnapshot?.switches?.[point.id]?.locked ? '锁闭' : '空闲' }}</span>
              </div>
            </div>
          </div>
          <div v-if="replaying" class="replay-control">
            <strong>只读事件回放</strong>
            <input v-model.number="replayIndex" type="range" min="0" :max="Math.max(0, replayFrames.length - 1)" aria-label="事件回放时间轴" />
            <span>{{ replayIndex + 1 }} / {{ replayFrames.length }} · 版本 {{ displaySnapshot?.version }}</span>
          </div>
          <div class="stage-legend" aria-label="区段与信号图例">
            <span><i class="swatch idle"></i>空闲</span><span><i class="swatch locked"></i>锁闭</span>
            <span><i class="swatch occupied"></i>占用</span><span><i class="swatch normal"></i>道岔定位</span>
            <span><i class="swatch reverse"></i>道岔反位</span><span><i class="joint-swatch"></i>绝缘节</span>
          </div>
          <div class="stage-tip" v-if="inspected"><strong>{{ inspected.type }} {{ inspected.name }}</strong><span>{{ inspected.state }}</span><button @click="inspected = null" aria-label="关闭设备详情">×</button></div>
        </div>
        <aside v-if="showIssues && station" class="issue-panel">
          <div class="panel-head"><strong>进路清单与数据问题</strong><button @click="showIssues = false" aria-label="关闭清单">×</button></div>
          <p>候选 {{ station.counts.candidate_routes }} 条：可办理 {{ station.counts.ready_routes }} 条，数据阻塞 {{ station.counts.blocked_routes }} 条。通过进路 {{ station.counts.excluded_routes }} 条属后续阶段。</p>
          <div v-if="station.routes" class="example-routes">
            <strong>操作示例</strong>
            <button v-for="id in exampleIds" :key="id" @click="selectExample(id)" type="button">{{ id }} 号 · {{ exampleKind(id) }}</button>
          </div>
          <div class="blocked-list">
            <strong>待核对的记录</strong>
            <div v-for="route in blockedRoutes" :key="route.id" class="blocked-route">
              <b>{{ route.id }} 号</b><span>联锁表第 {{ route.source_row }} 行</span>
              <small>{{ route.button_sequence.join(' → ') || '无按钮序列' }}</small>
              <p>{{ route.reasons.join('；') }}</p>
            </div>
          </div>
        </aside>
      </div>

      <footer class="console-footer">
        <div class="operation-row">
          <div class="selection-status">
            <span class="footer-label">按钮选择</span>
            <strong :class="{ blink: displaySnapshot?.selected_buttons?.length && !replaying }">{{ displaySnapshot?.selected_buttons?.join(' → ') || '等待始端按钮' }}</strong>
            <span v-if="displaySnapshot?.selected_buttons?.length" class="countdown">{{ displaySnapshot?.selection_remaining_seconds }} 秒</span>
          </div>
          <button type="button" class="action-button" :disabled="busy || replaying || !snapshot?.selected_buttons?.length" @click="clearSelection">清除未完成选择</button>
          <label class="scenario-select">区间许可场景
            <select v-model="intervalAvailable" :disabled="busy || replaying" aria-label="新会话区间许可场景">
              <option :value="true">普通站内 · 已具备</option>
              <option :value="false">条件反例 · 未具备</option>
            </select>
          </label>
          <label v-if="userStore.role !== 'student' && station" class="scenario-select">预置占用
            <select v-model="occupiedSection" :disabled="busy || replaying" aria-label="新会话预置占用区段">
              <option value="">无</option>
              <option v-for="section in station.sections" :key="section.id" :value="section.name">{{ section.name }}</option>
            </select>
          </label>
          <button type="button" class="action-button quiet" :disabled="busy || replaying" @click="newSession">{{ confirmNew ? '确认新建会话' : '新建仿真会话' }}</button>
        </div>
        <div class="message-row"><span class="message-dot"></span><strong>{{ displaySnapshot?.last_message || '正在准备站场' }}</strong><span class="version">状态版本 {{ displaySnapshot?.version ?? '—' }}</span></div>
        <div class="runtime-row">
          <div class="route-strip">
            <span class="footer-label">活动进路</span>
            <div v-if="!activeRoutes.length" class="empty-route">暂无。可按示例：XNLA → S5LA（1 号接车）。</div>
            <div v-for="route in activeRoutes" :key="route.id" class="route-card">
              <span><b>{{ route.route_id }} 号</b> {{ kindText(route.kind) }} · {{ route.status === 'signal_open' ? '信号开放' : route.status === 'clearing' ? '等待解锁' : '车辆运行' }}</span>
              <small>{{ route.sections.length }} 个区段 · 已推进 {{ Math.max(0, Math.min(route.progress + 1, route.sections.length)) }} 段</small>
              <button type="button" :disabled="busy || replaying || route.status === 'clearing' || userStore.role === 'student'" @click="advance(route.id)">{{ userStore.role === 'student' ? '由教师控制仿真行车' : route.progress === -2 ? '仿真行车 · 接近' : route.progress + 1 < route.sections.length ? '仿真行车 · 下一段' : '仿真行车 · 出清' }}</button>
            </div>
          </div>
          <div class="event-strip"><span class="footer-label">最近事件</span><span v-for="event in recentEvents" :key="event.version" class="event-line"><time>{{ eventTime(event.time) }}</time>{{ event.message }}</span></div>
        </div>
      </footer>
    </div>

    <div class="under-note">本操作台只执行计划书第一阶段的正常进路流程。总取消、总人解、区故解、上电解锁、通过与引导进路未开放；清除键只清掉未办成的临时选择。</div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/store/user'
import StationDiagram from './StationDiagram.vue'
import { advanceSimulationTrain, clearStationSelection, createSimulationSession, getSimulationReplay, getSimulationSnapshot, getStationPackage, pressStationButton } from './api'

const userStore = useUserStore()
const consoleRoot = ref(null)
const station = ref(null)
const snapshot = ref(null)
const loading = ref(true)
const busy = ref(false)
const isFullscreen = ref(false)
const showIssues = ref(false)
const showSwitches = ref(false)
const inspected = ref(null)
const intervalAvailable = ref(true)
const occupiedSection = ref('')
const confirmNew = ref(false)
const replaying = ref(false)
const replayFrames = ref([])
const replayIndex = ref(0)
const exampleIds = ['1', '16', '56', '115']
let poller = null
const storageKey = computed(() => `srtp-simulation-console-${userStore.user?.id || 'anonymous'}`)
const displaySnapshot = computed(() => replaying.value ? replayFrames.value[replayIndex.value] : snapshot.value)
const activeRoutes = computed(() => (displaySnapshot.value?.routes || []).filter(route => route.status !== 'released'))
const recentEvents = computed(() => (displaySnapshot.value?.events || []).slice(-4).reverse())
const blockedRoutes = computed(() => (station.value?.routes || []).filter(route => route.status === 'blocked'))

function kindText(kind) { return kind === 'train' ? '列车进路' : kind === 'short_shunt' ? '短调车' : '组合调车' }
function exampleKind(id) { return kindText(station.value?.routes?.find(route => route.id === id)?.kind) }
function eventTime(value) { return new Date(value).toLocaleTimeString('zh-CN', { hour12: false }) }
function onFullscreenChange() { isFullscreen.value = document.fullscreenElement === consoleRoot.value }
async function enterFullscreen() {
  if (document.fullscreenElement === consoleRoot.value) return true
  try { await consoleRoot.value?.requestFullscreen(); return true }
  catch { ElMessage.warning('浏览器未能进入全屏；请允许全屏后再操作'); return false }
}
async function toggleFullscreen() {
  if (isFullscreen.value) await document.exitFullscreen()
  else await enterFullscreen()
}
async function refresh() {
  if (!snapshot.value || busy.value) return
  try { snapshot.value = await getSimulationSnapshot(snapshot.value.session_id) }
  catch { /* Axios already reports authentication or session errors. */ }
}
async function boot() {
  loading.value = true
  try {
    station.value = await getStationPackage()
    const prior = sessionStorage.getItem(storageKey.value)
    if (prior) {
      try { snapshot.value = await getSimulationSnapshot(prior) }
      catch { sessionStorage.removeItem(storageKey.value) }
    }
    if (!snapshot.value) await startNewSession()
    intervalAvailable.value = snapshot.value.interval_available
  } finally { loading.value = false }
}
async function startNewSession() {
  snapshot.value = await createSimulationSession(intervalAvailable.value, occupiedSection.value ? [occupiedSection.value] : [])
  sessionStorage.setItem(storageKey.value, snapshot.value.session_id)
  confirmNew.value = false
}
async function openReplay() {
  if (!snapshot.value || busy.value) return
  try {
    replayFrames.value = await getSimulationReplay(snapshot.value.session_id)
    if (!replayFrames.value.length) return
    replayIndex.value = replayFrames.value.length - 1
    replaying.value = true
  } catch { ElMessage.error('读取事件回放失败') }
}
function closeReplay() { replaying.value = false }
async function newSession() {
  if (!confirmNew.value) { confirmNew.value = true; ElMessage.info('再点一次确认新建独立会话；当前会话的锁闭不会被清除'); return }
  busy.value = true
  try { await startNewSession() } finally { busy.value = false }
}
async function runCommand(action) {
  if (!snapshot.value || busy.value || replaying.value) return
  busy.value = true
  try {
    const response = await action(snapshot.value.session_id, snapshot.value.version)
    snapshot.value = response.snapshot
    if (!response.accepted) ElMessage.warning(response.message)
  } catch {
    try { snapshot.value = await getSimulationSnapshot(snapshot.value.session_id) } catch { /* Request layer reports the error. */ }
  } finally { busy.value = false }
}
async function pressButton(button) {
  if (replaying.value) return
  if (!(await enterFullscreen())) return
  await runCommand((id, version) => pressStationButton(id, button, version))
}
async function clearSelection() { await runCommand((id, version) => clearStationSelection(id, version)) }
async function advance(routeInstanceId) {
  if (replaying.value) return
  if (!(await enterFullscreen())) return
  await runCommand((id, version) => advanceSimulationTrain(id, routeInstanceId, version))
}
function inspectDevice(type, name, state) { inspected.value = { type, name, state } }
function showDisabled(message) { ElMessage.info(message) }
function selectExample(id) {
  const route = station.value?.routes?.find(item => item.id === id)
  if (!route) return
  showIssues.value = false
  ElMessage.info(`${id} 号${kindText(route.kind)}：请依次点击 ${route.button_sequence.join(' → ')}`)
}
onMounted(async () => {
  document.addEventListener('fullscreenchange', onFullscreenChange)
  try { await boot() } catch { ElMessage.error('操作台加载失败，请检查后端服务和登录状态') }
  poller = window.setInterval(refresh, 1000)
})
onBeforeUnmount(() => {
  document.removeEventListener('fullscreenchange', onFullscreenChange)
  if (poller) window.clearInterval(poller)
})
</script>

<style scoped>
.simulation-page { display: grid; gap: 18px; }
.page-intro { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }
.page-intro h1 { margin: 4px 0 10px; color: #183b60; font-size: 28px; font-weight: 600; }
.page-intro p:last-child { margin: 0; color: #61758a; font-size: 14px; line-height: 1.7; }
.eyebrow { margin: 0; color: #006fab; font-size: 11px; font-weight: 700; letter-spacing: 2px; }
.console-shell { display: flex; flex-direction: column; width: 100%; height: min(830px, 76vh); min-height: 570px; overflow: hidden; border: 1px solid #254760; border-radius: 9px; background: #08121c; color: #dce7f0; box-shadow: 0 18px 36px #14345c1a; }
.console-shell:fullscreen, .console-shell.is-fullscreen { width: 100vw; height: 100vh; min-height: 0; border: 0; border-radius: 0; }
.console-header { display: flex; align-items: center; gap: 18px; min-height: 61px; padding: 9px 17px; border-bottom: 1px solid #24445e; background: #0b2947; }
.console-brand { display: flex; align-items: center; gap: 10px; white-space: nowrap; }
.brand-mark { padding: 7px 6px; border: 1px solid #b79959; color: #ecd29a; font: 700 13px Georgia, serif; letter-spacing: 1px; }
.console-brand div { display: grid; gap: 3px; }
.console-brand strong { font-size: 15px; letter-spacing: 1px; }
.console-brand small { font-size: 10px; color: #9ebad1; }
.console-summary { display: flex; flex-wrap: wrap; gap: 7px 14px; margin-left: auto; color: #acc1d4; font-size: 11px; }
.status-ready { color: #79d1a0; }.status-blocked { color: #f3c56b; }
.console-header-actions { display: flex; gap: 8px; }
.chrome-button, .action-button { border: 1px solid #57718a; border-radius: 3px; padding: 8px 12px; background: #15324c; color: #f0f5f7; white-space: nowrap; }
.chrome-button:hover, .action-button:hover:not(:disabled) { border-color: #8cbbdd; background: #234966; }
.chrome-button.primary { border-color: #2985be; background: #006fae; }
.console-body { position: relative; display: flex; flex: 1; min-height: 0; overflow: hidden; }
.stage-wrap { position: relative; flex: 1; min-width: 0; overflow: auto; background: #05090e; }
.switch-status-panel { position: absolute; top: 14px; right: 18px; z-index: 2; width: 225px; max-height: 180px; border: 1px solid #47657c; background: #102235ee; box-shadow: 0 8px 20px #0007; color: #d8e6ee; font-size: 11px; }
.switch-panel-head { display: flex; justify-content: space-between; align-items: center; padding: 6px 9px; background: #163952; color: #e6eef4; font-size: 12px; }
.switch-panel-head button { border: 0; background: transparent; color: #d8e6ee; font-size: 17px; line-height: 1; cursor: pointer; }
.switch-status-heading, .switch-status-row { display: grid; grid-template-columns: 48px 1fr 48px; align-items: center; gap: 7px; padding: 4px 9px; }
.switch-status-heading { border-bottom: 1px solid #526a7b; color: #9fb8c8; }
.switch-status-list { max-height: 119px; overflow-y: auto; }
.switch-status-row:nth-child(even) { background: #18314888; }
.switch-status-row span:nth-child(2) { display: flex; align-items: center; gap: 5px; }
.switch-lamp { display: inline-block; width: 8px; height: 8px; border-radius: 50%; border: 1px solid #b9eac5; background: #65e344; }
.switch-lamp.reverse { border-color: #f6dda0; background: #f4ca47; }
.stage-legend { position: absolute; top: 15px; left: 18px; display: flex; gap: 14px; padding: 9px 12px; border: 1px solid #364b5f; background: #091724dd; color: #becbd7; font-size: 11px; }
.stage-legend span { display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; }
.swatch { display: inline-block; width: 14px; height: 4px; }.idle { background: #5b83b1; }.locked { background: #f3f4f4; }.occupied { background: #f04448; }.normal { background: #65e344; }.reverse { background: #f4ca47; }
.joint-swatch { display: inline-block; width: 2px; height: 12px; margin: 0 5px; background: #aebbc3; }
.stage-tip { position: absolute; right: 20px; top: 15px; display: flex; align-items: center; gap: 10px; padding: 9px 12px; border: 1px solid #687f91; background: #10263be8; font-size: 12px; }
.stage-tip strong { color: #f2d184; }.stage-tip button, .panel-head button { border: 0; background: none; color: #dce7f0; font-size: 20px; }
.replay-control { position: absolute; left: 18px; bottom: 16px; z-index: 3; display: flex; align-items: center; gap: 12px; max-width: calc(100% - 36px); padding: 11px 14px; border: 1px solid #927d4a; border-radius: 3px; background: #122b43ed; color: #f1e3bc; font-size: 12px; box-shadow: 0 8px 22px #0008; }
.replay-control input { width: min(340px, 30vw); accent-color: #e4bb64; }
.issue-panel { flex: 0 0 355px; overflow-y: auto; padding: 15px; border-left: 1px solid #29495d; background: #102236; color: #b8cbd8; font-size: 12px; line-height: 1.6; }
.panel-head { display: flex; justify-content: space-between; align-items: center; color: #f4f7fa; font-size: 15px; }
.example-routes { display: grid; gap: 7px; margin: 20px 0; }
.example-routes button { padding: 6px 8px; border: 1px solid #456783; border-radius: 3px; background: #163550; color: #eaf2f8; text-align: left; }
.blocked-list { display: grid; gap: 8px; }.blocked-route { border-top: 1px solid #3b5368; padding: 8px 0 2px; }.blocked-route b { color: #f4c778; margin-right: 10px; }.blocked-route small { display: block; color: #a8c1d2; }.blocked-route p { margin: 4px 0; }
.console-footer { flex: 0 0 auto; border-top: 1px solid #2d4b61; background: #0b2135; }
.operation-row, .message-row { display: flex; align-items: center; gap: 12px; padding: 8px 14px; border-bottom: 1px solid #274055; }
.selection-status { display: flex; align-items: center; gap: 8px; flex: 1; min-width: 0; }
.selection-status strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #f2d584; font-size: 12px; }
.footer-label { color: #8fb4ce; font-size: 11px; white-space: nowrap; }
.countdown { padding: 3px 5px; border: 1px solid #8e6b31; color: #f2cc73; font-size: 11px; }
.scenario-select { display: flex; align-items: center; gap: 7px; color: #a8c4d8; font-size: 11px; white-space: nowrap; }
.scenario-select select { max-width: 168px; padding: 6px; border: 1px solid #56738b; border-radius: 3px; background: #122f49; color: #e3eef6; }
.action-button { font-size: 11px; }.action-button:disabled { cursor: not-allowed; opacity: .48; }.action-button.quiet { border-color: #65798a; background: #233748; }
.message-row { color: #e7eef4; font-size: 12px; }.message-dot { flex: 0 0 7px; height: 7px; border-radius: 50%; background: #71c190; }.message-row strong { flex: 1; font-weight: 500; }.version { color: #8aa9be; white-space: nowrap; }
.runtime-row { display: flex; gap: 15px; height: 120px; padding: 10px 14px; overflow: auto; }
.route-strip { display: flex; align-items: flex-start; gap: 9px; flex: 1; overflow-x: auto; }.empty-route { color: #a7b9c7; font-size: 12px; }
.route-card { display: grid; flex: 0 0 auto; gap: 3px; min-width: 185px; padding: 5px 8px; border: 1px solid #4c6780; background: #122f49; font-size: 11px; }.route-card b { color: #f2d584; }.route-card small { color: #9ab5c7; }.route-card button { margin-top: 3px; border: 1px solid #0f82bb; background: #0b5f94; color: white; font-size: 11px; }.route-card button:disabled { opacity: .5; cursor: not-allowed; }
.event-strip { display: grid; align-content: start; flex: 0 0 36%; gap: 4px; border-left: 1px solid #30495e; padding-left: 13px; font-size: 11px; color: #c0d0dc; }.event-line { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.event-line time { color: #779eb7; margin-right: 7px; }
.under-note { color: #657b90; font-size: 12px; line-height: 1.6; }
.blink { animation: waiting 1s steps(2) infinite; }@keyframes waiting { 50% { opacity: .38; } }
@media (max-width: 1100px) { .console-summary { display: none; }.runtime-row .event-strip { display: none; }.scenario-select { display: none; } }
</style>
