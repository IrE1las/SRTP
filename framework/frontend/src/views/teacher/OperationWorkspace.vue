<template>
  <div class="op-workspace" v-loading="loading">
    <a class="skip-link" href="#operation-station">跳转到站场</a>
    <header class="op-workspace-header">
      <router-link :to="destination(questionId)" class="op-workspace-back">← 题目设置</router-link>
      <div class="op-workspace-title"><h1>{{ current?.title || '未命名题目' }}</h1><span>v{{ entryVersion }} · {{ kind === 'preview' ? '题目预览' : '标准答案录制' }}</span></div>
      <nav class="op-workspace-steps" aria-label="出题流程"><span>1 题目设置</span><strong aria-current="step">2 录制答案</strong><router-link :to="destination(questionId, 'review')">3 检查发布</router-link></nav>
    </header>
    <div class="op-workspace-toolbar">
      <div class="op-workspace-state"><span class="op-status" :class="consoleResult?.status || ''">{{ sessionId ? sessionStatus(consoleResult?.status || 'active') : '尚未开始' }}</span><span v-if="sessionId" class="op-number">{{ consoleResult?.revision || 0 }} 次点击已确认</span><span v-if="entryReadOnly" class="op-archive-label">其他教师的记录 · 只读</span><span v-if="isHistorical" class="op-archive-label">历史记录 · v{{ entryVersion }}</span></div>
      <div class="op-workspace-controls">
        <el-button @click="drawer = 'task'">查看题干</el-button><el-button @click="drawer = 'records'">历史记录</el-button><el-button v-if="sessionId" @click="drawer = 'log'">操作日志</el-button>
        <el-button v-if="!entryReadOnly && current?.disabled && consoleResult?.status === 'active'" type="primary" :loading="working" @click="finish">结束当前记录</el-button>
        <template v-if="!current?.disabled && !isHistorical && !entryReadOnly">
          <el-button v-if="!sessionId" type="primary" :loading="working" @click="start">{{ kind === 'preview' ? '开始预览' : '开始录制' }}</el-button>
          <el-button v-else-if="consoleResult?.status === 'active'" type="primary" :loading="working" @click="finish">{{ kind === 'preview' ? '结束预览' : '结束录制' }}</el-button>
          <template v-else-if="consoleResult"><el-button :loading="working" @click="start">{{ kind === 'preview' ? '重新预览' : '重新录制' }}</el-button><el-button v-if="canSaveStandard" type="primary" :loading="working" @click="saveStandard">保存答案并检查发布 →</el-button><router-link v-else :to="destination(questionId, 'review')">检查发布 →</router-link></template>
        </template>
      </div>
    </div>
    <div v-if="notice" class="op-workspace-notice" role="alert"><span>{{ notice }}</span><el-button v-if="loadFailed" @click="load">重新加载</el-button></div>
    <div v-if="current?.disabled" class="op-workspace-notice">题目已停用，不能新开录制或预览，原记录仍可查看。</div>
    <div v-if="consoleResult?.status === 'stopped' && kind === 'recording' && !consoleResult.events?.length" class="op-workspace-notice">本次没有记录业务点击，请重新录制后再保存标准答案。</div>
    <main id="operation-station" class="op-station-main" tabindex="-1">
      <OperationConsole v-if="sessionId" :key="sessionId" ref="consoleRef" :session-id="sessionId" :read-only="entryReadOnly" @update="consoleResult = $event" />
      <div v-else-if="current && !loading" class="op-workspace-ready"><div class="op-ready-station" aria-hidden="true"><span></span><i></i><span></span></div><h2>{{ kind === 'preview' ? '从初始条件预览题目' : '准备录制标准答案' }}</h2><p>区间许可{{ current.initial.interval_available ? '具备' : '不具备' }} · {{ current.initial.occupied_sections.length ? '占用：' + current.initial.occupied_sections.join('、') : '全部区段空闲' }}</p><p>开始后，在站场完成操作，再点击{{ kind === 'preview' ? '“结束预览”' : '“结束录制”，保存为标准答案' }}。</p><el-button v-if="!current.disabled" type="primary" :loading="working" @click="start">{{ kind === 'preview' ? '开始预览' : '开始录制' }}</el-button></div>
    </main>
    <el-drawer :model-value="!!drawer" :title="drawerTitle" :size="drawerSize" class="op-record-drawer" @update:model-value="value => { if (!value) drawer = '' }">
      <div class="op-drawer-content">
        <template v-if="drawer === 'task'"><h2>{{ task?.title || '未命名题目' }}</h2><p class="op-preserve">{{ task?.prompt || '尚未填写任务说明。' }}</p><p class="op-help">题设版本 v{{ task?.number }}<span v-if="isHistorical"> · 历史记录</span></p><h3>初始条件</h3><p>区间许可：{{ task?.initial.interval_available ? '具备' : '不具备' }}</p><p>预置占用：{{ task?.initial.occupied_sections.join('、') || '全部空闲' }}</p></template>
        <template v-else-if="drawer === 'log'"><p class="op-help">只显示服务端已确认的点击。重新同步会沿用原事件，连续重复点击分别保留。</p><div class="op-drawer-actions"><span>{{ consoleResult?.events?.length || 0 }} 条记录</span><el-button :loading="downloading" @click="download(sessionId)">下载日志</el-button></div><OperationLog :events="consoleResult?.events || []" /></template>
        <template v-else-if="drawer === 'records'"><p class="op-help">重新录制会创建新记录，旧记录会保留。</p><el-empty v-if="!current?.sessions?.length" :image-size="80" description="尚无录制或预览记录" /><div v-for="item in sessionPage.items" :key="item.id" class="op-history-item"><div><strong>{{ item.kind === 'preview' ? '预览' : '标准录制' }} · v{{ versionNumber(item.version_id) }}</strong><p>{{ sessionStatus(item.status) }}{{ item.id === sessionId ? ' · 当前记录' : '' }}</p></div><div class="op-actions-group"><el-button v-if="item.id !== sessionId" @click="openSession(item)">{{ item.owner_id === user.user?.id && item.status === 'active' ? '继续操作' : '查看' }}</el-button><el-button link :loading="downloading" @click="download(item.id)">下载</el-button></div></div><ListPager :page="sessionPage.page" :total="sessionPage.total" @change="recordsPage = $event" /></template>
      </div>
    </el-drawer>
  </div>
</template>
<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessageBox } from 'element-plus'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/store/user'
import OperationConsole from '@/features/simulationConsole/OperationConsole.vue'
import OperationLog from '@/features/operationQuestions/OperationLog.vue'
import ListPager from '@/components/ListPager.vue'
import { paginate } from '@/domain/pagination'
import { operationLocation, operationReturn, sessionStatus, operationError, canSaveRecording } from '@/domain/operationPresentation'
import { getOperation, getOperationVersion, startOperationSession, stopOperationSession, saveOperationStandard, downloadOperationLog } from '@/api/operations'
import '@/features/operationQuestions/operation.css'
const route = useRoute(), router = useRouter(), user = useUserStore()
const backTo = computed(() => operationReturn(route.query.back))
function destination(id, step = 'edit', query = {}) { return operationLocation(id, step, backTo.value, query) }
const current = ref(null), sessionId = ref(''), consoleResult = ref(null), consoleRef = ref(null), loading = ref(false), working = ref(false), loadFailed = ref(false), notice = ref(''), drawer = ref(''), recordsPage = ref(1), downloading = ref(false)
const task = ref(null)
const questionId = computed(() => route.params.questionId)
const entry = computed(() => current.value?.sessions?.find(item => item.id === sessionId.value))
const entryReadOnly = computed(() => !!entry.value && entry.value.owner_id !== user.user?.id)
const kind = computed(() => entry.value?.kind || (route.query.mode === 'preview' || current.value?.status === 'published' ? 'preview' : 'recording'))
const entryVersion = computed(() => versionNumber(entry.value?.version_id) || current.value?.number || 1)
const isHistorical = computed(() => !!entry.value && entry.value.version_id !== current.value?.version_id)
const sessionPage = computed(() => paginate(current.value?.sessions || [], recordsPage.value))
const canSaveStandard = computed(() => !entryReadOnly.value && !!consoleResult.value?.events?.length && canSaveRecording(current.value, consoleResult.value, current.value?.sessions || [], sessionId.value))
const drawerTitle = computed(() => ({ task: '题目与初始条件', records: '录制与预览记录', log: '操作日志' })[drawer.value] || '')
const drawerSize = computed(() => drawer.value === 'log' ? 'min(900px, 94vw)' : 'min(620px, 94vw)')
let loadToken = 0, navigatingAfterSave = false
function versionNumber(id) { return current.value?.versions?.find(item => item.id === id)?.number || (id === current.value?.version_id ? current.value?.number : null) }
async function load() {
  const token = ++loadToken
  loading.value = true; loadFailed.value = false; notice.value = ''
  if (current.value && String(current.value.id) !== String(questionId.value)) { current.value = null; sessionId.value = ''; consoleResult.value = null }
  try {
    const data = await getOperation(questionId.value)
    if (token !== loadToken) return
    let selected
    if (route.query.session) {
      selected = data.sessions.find(item => item.id === route.query.session)
      if (!selected) throw new Error('该记录不存在，请从题目历史记录中重新选择。')
    } else selected = data.sessions.find(item => item.version_id === data.version_id && item.owner_id === user.user?.id && item.status === 'active')
    const number = data.versions.find(item => item.id === selected?.version_id)?.number
    const taskData = number && number !== data.number ? await getOperationVersion(data.id, number) : data
    if (token !== loadToken) return
    current.value = data; task.value = taskData
    if (sessionId.value !== (selected?.id || '')) consoleResult.value = null
    sessionId.value = selected?.id || ''
    if (selected && !route.query.session) await router.replace({ path: route.path, query: { ...route.query, session: selected.id } })
  } catch (error) { if (token === loadToken) { sessionId.value = ''; consoleResult.value = null; loadFailed.value = true; notice.value = operationError(error) } }
  finally { if (token === loadToken) loading.value = false }
}
async function start() {
  if (working.value || entryReadOnly.value || !current.value || current.value.disabled || isHistorical.value) return
  if (sessionId.value) {
    try { await ElMessageBox.confirm('将从题设初始条件重新开始，原操作日志会保留。', kind.value === 'preview' ? '重新预览' : '重新录制', { confirmButtonText: '重新开始', cancelButtonText: '取消' }) } catch { return }
  }
  working.value = true; notice.value = ''
  try {
    await consoleRef.value?.flush()
    const data = await startOperationSession(current.value.id, kind.value)
    consoleResult.value = data
    current.value = await getOperation(current.value.id)
    sessionId.value = data.session_id
    await router.replace({ path: route.path, query: { ...route.query, session: data.session_id } })
  } catch (error) { notice.value = operationError(error) } finally { working.value = false }
}
async function finish() {
  if (working.value || entryReadOnly.value || consoleResult.value?.status !== 'active') return
  working.value = true; notice.value = ''
  try {
    await consoleRef.value.flush()
    consoleResult.value = await stopOperationSession(sessionId.value)
    consoleRef.value.sync(consoleResult.value)
    current.value = await getOperation(current.value.id)
  } catch (error) { notice.value = operationError(error) } finally { working.value = false }
}
async function saveStandard() {
  if (!canSaveStandard.value || working.value) return
  working.value = true; notice.value = ''
  try {
    await consoleRef.value.flush()
    await saveOperationStandard(sessionId.value)
    navigatingAfterSave = true
    await router.push(destination(current.value.id, 'review'))
  } catch (error) { notice.value = operationError(error) } finally { navigatingAfterSave = false; working.value = false }
}
async function download(id) { downloading.value = true; try { await downloadOperationLog(id) } catch (error) { notice.value = operationError(error) } finally { downloading.value = false } }
function openSession(item) { drawer.value = ''; return router.push({ path: route.path, query: { ...(backTo.value === '/operations/manage' ? {} : { back: backTo.value }), session: item.id } }) }
async function confirmLeave() {
  if (entryReadOnly.value) return true
  if (working.value) return false
  try { await consoleRef.value?.flush() } catch (error) { notice.value = operationError(error); return false }
  if (entryReadOnly.value || consoleResult.value?.status !== 'active') return true
  try { await ElMessageBox.confirm('当前记录已保存，离开后可从历史记录继续操作。', '暂时离开操作台', { confirmButtonText: '离开操作台', cancelButtonText: '继续操作' }); return true } catch { return false }
}
function beforeUnload(event) { if (consoleRef.value?.hasUnconfirmed) { event.preventDefault(); event.returnValue = '' } }
onBeforeRouteLeave(async () => navigatingAfterSave || await confirmLeave())
onBeforeRouteUpdate(async to => {
  if (working.value) return to.params.questionId === route.params.questionId && to.query.session === sessionId.value
  if (to.params.questionId === route.params.questionId && to.query.session === route.query.session) return true
  return await confirmLeave()
})
watch(() => [route.params.questionId, route.query.session], load, { immediate: true })
onMounted(() => window.addEventListener('beforeunload', beforeUnload))
onBeforeUnmount(() => { loadToken++; window.removeEventListener('beforeunload', beforeUnload) })
</script>
<style scoped>
.op-workspace{height:100dvh;min-height:680px;display:flex;flex-direction:column;background:#eef3f8;color:#19334d;padding-bottom:env(safe-area-inset-bottom)}.op-workspace-header{display:flex;align-items:center;gap:26px;padding:12px 24px;background:#093278;color:white;min-height:74px}.op-workspace-back{color:#e2edf9;font-size:14px;flex-shrink:0;padding:9px 0}.op-workspace-back:hover{text-decoration:underline}.op-workspace-title{min-width:0;flex:1}.op-workspace-title h1{font-size:18px;font-weight:600;margin:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.op-workspace-title>span{font-size:13px;color:#c7d9ee}.op-workspace-steps{display:flex;gap:18px;font-size:13px;color:#d0def0;white-space:nowrap}.op-workspace-steps strong{color:white}.op-workspace-steps a{color:#d0def0}.op-workspace-steps a:hover{color:white;text-decoration:underline}.op-workspace-toolbar{display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap;padding:12px 24px;background:white;border-bottom:1px solid #dce5ef}.op-workspace-state,.op-workspace-controls{display:flex;gap:12px;align-items:center;flex-wrap:wrap}.op-workspace-state{font-size:13px;color:#586f82}.op-workspace-controls .el-button{font-size:14px;min-height:40px;padding:8px 12px}.op-workspace-controls>a{font-size:14px}.op-archive-label{color:#8a5b1e}.op-station-main{flex:1;min-height:0;padding:16px 22px 12px;display:flex;flex-direction:column}.op-workspace-notice{padding:10px 24px;display:flex;align-items:center;gap:16px;background:#fff4e9;color:#9b4b28;font-size:14px}.op-workspace-ready{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;border:1px solid #dce5ef;border-radius:8px;background:white;padding:24px;gap:12px}.op-workspace-ready h2{font-size:22px;margin:4px 0}.op-workspace-ready p{font-size:15px;color:#586f82;margin:0;max-width:700px;overflow-wrap:anywhere}.op-workspace-ready .el-button{margin-top:14px}.op-ready-station{width:180px;display:flex;align-items:center;gap:12px;margin-bottom:18px}.op-ready-station span{height:3px;flex:1;background:#b6cddd}.op-ready-station i{width:26px;height:26px;background:#e3f2fb;border:5px solid #448ab5;border-radius:50%}.op-drawer-actions{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:16px}.op-drawer-content h2{font-size:21px;overflow-wrap:anywhere}.op-drawer-content p{line-height:1.9}.op-drawer-content h3{margin-top:28px;font-size:17px}
@media(max-width:1100px){.op-workspace-steps{display:none}.op-workspace-toolbar{padding:10px 16px}.op-station-main{padding:12px}.op-workspace-header{padding:12px 16px;gap:18px}}
@media(max-width:650px){.op-workspace{height:auto;min-height:100dvh}.op-station-main{min-height:660px}.op-workspace-controls{gap:6px}.op-workspace-controls .el-button{font-size:13px;padding:8px}.op-workspace-title h1{font-size:16px}.op-workspace-back{font-size:13px}.op-workspace-ready{min-height:480px}}
</style>
