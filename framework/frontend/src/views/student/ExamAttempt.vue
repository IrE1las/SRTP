<template>
  <main class="exam-shell exam-page" :class="{ 'exam-running': attempt?.status === 'active' }" :aria-busy="loading">
    <p v-if="notice" class="exam-notice" role="alert">{{ notice }}</p>
    <div v-if="!attempt" class="exam-loading"><h1>考试记录</h1><p>{{ loading ? '正在同步考试状态…' : '尚未读取考试，请保留页面并重试。' }}</p><el-button @click="initialize">重新同步</el-button><router-link to="/student/exams">返回考试界面</router-link></div>
    <template v-else-if="attempt.status === 'submitted'">
      <section class="exam-finished">
        <div class="exam-finish-heading">
          <div><h1>{{ attempt.message || completedMessage }}</h1><h2>{{ attempt.name }}</h2></div>
          <router-link class="el-button el-button--primary exam-return-button" :to="{path:'/student/exams/history',query:{page:route.query.back || 1}}"><span aria-hidden="true">←</span>返回历史考试</router-link>
        </div>
        <dl class="exam-facts"><div><dt>交卷原因</dt><dd>{{ attempt.finish_reason_text }}</dd></div><div><dt>交卷时间（北京时间）</dt><dd>{{ beijingTime(attempt.submitted_at) }}</dd></div><div><dt>已保存的业务操作</dt><dd>{{ attempt.console?.events?.length ?? 0 }} 条</dd></div></dl>
        <section v-if="attempt.grade" class="exam-published-grade" aria-label="已发布成绩"><div><span>最终成绩</span><strong>{{ attempt.grade.score }}<small> / 100</small></strong></div><div><p v-if="attempt.grade.comment" class="op-preserve">{{ attempt.grade.comment }}</p><p class="op-help">第 {{ attempt.grade.version }} 版 · 发布于 {{ beijingTime(attempt.grade.published_at) }}</p></div></section>
        <div class="op-actions-group"><el-button :loading="loading" @click="initialize">刷新成绩</el-button><el-button @click="download">下载本人日志</el-button></div>
        <OperationLog :events="attempt.console?.events || []" title="本人操作日志" />
      </section>
    </template>
    <template v-else>
      <header class="exam-header"><div><p class="exam-kicker">标准站 · 正式作答</p><h1 :title="attempt.name">{{ attempt.name }}</h1><p>开放 {{ beijingTime(attempt.opens_at) }}　截止 {{ beijingTime(attempt.closes_at) }}　允许 {{ attempt.duration_minutes }} 分钟</p></div><div class="exam-countdown"><span>剩余时间</span><strong :class="{urgent:remaining <= 60}">{{ clockText(remaining) }}</strong></div><div class="exam-live-actions"><el-button :disabled="refreshing || submitting" :loading="refreshing" @click="refreshExam">刷新考试</el-button><el-button type="primary" :disabled="paused || submitting || refreshing" :loading="submitting" @click="submit">提交试卷</el-button></div></header>
      <section class="exam-prompt"><div><h2>{{ attempt.question.title }}</h2><p class="exam-prompt-preview">{{ attempt.question.prompt }}</p></div><el-button text @click="questionOpen = true">完整题干</el-button></section>
      <el-dialog v-model="questionOpen" title="完整题干" width="min(720px, 94vw)" :append-to-body="false"><div class="exam-question-full"><h2>{{ attempt.question.title }}</h2><p>{{ attempt.question.prompt }}</p></div></el-dialog>
      <section v-if="paused" class="exam-paused" role="status" aria-live="polite">
        <template v-if="!connected"><h2>连接中断，操作已暂停</h2><p>考试继续计时。恢复网络后将同步原答卷与未确认记录。</p></template>
        <template v-else-if="remaining === 0"><h2>作答时间已到，正在确认交卷</h2><p>收到服务端确认后显示完成状态。</p></template>
        <template v-else-if="!isFullscreen || attempt.fullscreen_state === 'outside'"><h2>已退出全屏 {{ attempt.exit_count }} 次</h2><p>恢复期限剩余 {{ restoreRemaining }} 秒；第二次退出立即交卷，考试总计时继续。</p><el-button type="primary" :disabled="restoring" @click="restoreFullscreen">恢复全屏</el-button></template>
        <template v-else><h2>正在核对考试状态</h2><p>全屏与操作记录同步后可继续作答。</p></template>
        <el-button :disabled="syncing || refreshing" :loading="refreshing" @click="refreshExam">刷新考试</el-button>
      </section>
      <section class="exam-station"><OperationConsole v-if="journalReady" ref="consoleRef" :session-id="sid" :read-only="paused || submitting || refreshing" :pause-pending="paused" :api="consoleApi" exam-mode /></section>
    </template>
  </main>
</template>
<script setup>
import '@/features/exams/exam.css'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute } from 'vue-router'
import OperationConsole from '@/features/simulationConsole/OperationConsole.vue'
import OperationLog from '@/features/operationQuestions/OperationLog.vue'
import { getExamAttempt, syncExam, submitExam, examStation, examEvent, downloadExam, reportExamExit } from '@/api/exams'
import { ExamJournal, beijingTime, secondsLeft, clockText, completedMessage, examError } from '@/domain/exams'
const route = useRoute(), sid = String(route.params.attemptId), attempt = ref(null), consoleRef = ref(null)
const loading = ref(true), notice = ref(''), connected = ref(navigator.onLine), isFullscreen = ref(!!document.fullscreenElement), journalReady = ref(false)
const syncing = ref(false), submitting = ref(false), restoring = ref(false), estimatedNow = ref(Date.now()), pending = ref(true)
const refreshing = ref(false), questionOpen = ref(false)
let journal, inFlight = null, timer, disposed = false, finished = false, serverAnchor = Date.now(), performanceAnchor = performance.now(), serverOffset = 0
const remaining = computed(() => attempt.value ? secondsLeft(attempt.value.deadline, estimatedNow.value) : 0)
const restoreRemaining = computed(() => attempt.value?.restore_deadline ? secondsLeft(attempt.value.restore_deadline, estimatedNow.value) : 60)
const paused = computed(() => !connected.value || !isFullscreen.value || pending.value || !attempt.value || attempt.value.fullscreen_state !== 'inside' || remaining.value <= 0 || !journalReady.value)
function capture(fullscreen) {
  if (!journal || finished) return
  try { journal.observe(fullscreen); pending.value = journal.pending.length > 0 }
  catch (error) { journalReady.value = false; notice.value = error.message }
}
async function accept(data) {
  if (disposed) return
  if (attempt.value && (data.revision < attempt.value.revision || attempt.value.status === 'submitted' && data.status !== 'submitted')) return
  if (attempt.value?.grade && (!data.grade || data.grade.version < attempt.value.grade.version)) return
  attempt.value = data; serverOffset = Date.parse(data.server_now) - Date.now()
  serverAnchor = Date.parse(data.server_now); performanceAnchor = performance.now(); estimatedNow.value = serverAnchor
  if (data.status === 'submitted') {
    finished = true; pending.value = false
    if (document.fullscreenElement) await document.exitFullscreen().catch(() => {})
  }
}
async function synchronize() {
  if (disposed || !journalReady.value || !navigator.onLine) { connected.value = false; return attempt.value }
  if (inFlight) return inFlight
  syncing.value = true
  inFlight = (async () => {
    try {
      // New exits captured while this request is in flight remain in storage.
      capture(!!document.fullscreenElement)
      journal.read()
      const data = await syncExam(sid, { fullscreen: !!document.fullscreenElement, events: [...journal.pending] })
      journal.acknowledge(data.acknowledged_events); pending.value = journal.pending.length > 0
      connected.value = navigator.onLine
      await accept(data)
      if (!pending.value) notice.value = ''
      return data
    } catch (error) {
      connected.value = false; notice.value = examError(error, '考试状态尚未确认，操作已暂停；请保留页面并重试。')
      throw error
    } finally { syncing.value = false; loading.value = false; inFlight = null }
  })()
  return inFlight
}
const consoleApi = {
  station: examStation,
  console: async () => { const data = await synchronize(); if (!data?.console) throw new Error('考试状态未确认'); return data.console },
  event: async (id, event) => {
    if (paused.value || !navigator.onLine || !document.fullscreenElement) throw new Error('考试操作已暂停')
    return examEvent(id, event)
  },
}
function observeFullscreen() {
  isFullscreen.value = !!document.fullscreenElement; capture(isFullscreen.value)
  if (!finished) synchronize().catch(() => {})
}
function offline() { connected.value = false }
function online() { synchronize().catch(() => {}) }
async function refreshExam() {
  if (refreshing.value || submitting.value) return
  refreshing.value = true
  try {
    if (!navigator.onLine) throw new Error('网络尚未恢复')
    const data = await synchronize()
    if (!data?.console) throw new Error('考试状态尚未确认')
    consoleRef.value?.sync(data.console)
    if (data.status === 'active') await consoleRef.value?.recover()
    notice.value = ''
  } catch (error) { notice.value = examError(error, error.message || '刷新失败，请保留页面并重试。') }
  finally { refreshing.value = false }
}
function beforeUnload() {
  capture(false)
  if (!finished && journalReady.value && navigator.onLine) {
    reportExamExit(sid, [...journal.pending]).catch(() => {})
  }
}
async function restoreFullscreen() {
  restoring.value = true
  try { await document.documentElement.requestFullscreen(); observeFullscreen(); await synchronize() }
  catch (error) { notice.value = examError(error, '全屏尚未恢复，请重试；恢复期限继续计时。') }
  finally { restoring.value = false }
}
async function submit() {
  if (paused.value || submitting.value) return
  submitting.value = true
  try {
    const console = await consoleRef.value.flush()
    const latest = await synchronize()
    if (latest?.status === 'submitted') return
    if (paused.value) throw new Error('请先同步考试状态')
    const data = await submitExam(sid, console.revision)
    await accept(data)
  } catch (error) { notice.value = examError(error, '交卷尚未确认，请同步未确认操作后重试。') }
  finally { submitting.value = false }
}
async function download() { try { await downloadExam(sid) } catch (error) { notice.value = examError(error) } }
async function leaveAttempt() {
  if (finished) return true
  if (submitting.value) return false
  capture(false)
  try {
    // Leave in the persistent exit episode, even if the fullscreen element has not yet changed.
    if (journalReady.value && navigator.onLine) {
      const data = await syncExam(sid, { fullscreen: false, events: [...journal.pending] })
      journal.acknowledge(data.acknowledged_events); await accept(data)
    }
  } catch { /* journal remains durable for re-entry */ }
  if (document.fullscreenElement) await document.exitFullscreen().catch(() => {})
  return true
}
onBeforeRouteLeave(leaveAttempt)
onBeforeRouteUpdate(leaveAttempt)
async function initialize() {
  if (loading.value && journal) return
  loading.value = true
  try {
    journal = new ExamJournal(localStorage, 'srtp-exam-control-' + sid, () => Date.now() + serverOffset)
    // Clock calibration precedes capture on re-entry; pending event times stay unchanged.
    await accept(await getExamAttempt(sid))
    journalReady.value = true
    if (!finished) { capture(!!document.fullscreenElement); await synchronize() }
  } catch (error) { notice.value = examError(error, error.message || '考试加载失败，请重试。') }
  finally { loading.value = false }
}
onMounted(() => {
  document.addEventListener('fullscreenchange', observeFullscreen)
  window.addEventListener('offline', offline); window.addEventListener('online', online); window.addEventListener('beforeunload', beforeUnload)
  window.addEventListener('pagehide', beforeUnload)
  initialize()
  timer = setInterval(() => {
    estimatedNow.value = serverAnchor + performance.now() - performanceAnchor
    if (journalReady.value && !finished && !syncing.value && navigator.onLine) synchronize().catch(() => {})
  }, 1000)
})
onBeforeUnmount(() => { disposed = true; clearInterval(timer); document.removeEventListener('fullscreenchange', observeFullscreen); window.removeEventListener('offline', offline); window.removeEventListener('online', online); window.removeEventListener('beforeunload', beforeUnload); window.removeEventListener('pagehide', beforeUnload) })
</script>
<style scoped>
.exam-shell{min-height:100dvh;background:#f1f5f9;color:#19334d;padding:20px 24px;font-family:'Microsoft YaHei',sans-serif}.exam-header{display:flex;gap:24px;align-items:center;background:#fff;border-top:4px solid #093278;padding:18px 22px}.exam-header>div:first-child{flex:1;min-width:0}.exam-header h1{font-size:23px;margin:0 0 8px;overflow-wrap:anywhere}.exam-header p{font-size:13px;line-height:1.9;color:#586f82;margin:0}.exam-countdown{display:grid;gap:2px;min-width:120px;text-align:center}.exam-countdown span{font-size:13px;color:#586f82}.exam-countdown strong{font-family:Consolas,monospace;font-size:32px;font-variant-numeric:tabular-nums;color:#093278}.exam-countdown .urgent{color:#b54732}.exam-prompt{background:white;border:1px solid #dfe7ef;padding:16px 22px;margin:14px 0}.exam-prompt h2{font-size:17px;margin:0 0 8px}.exam-prompt p{font-size:15px;line-height:1.8;white-space:pre-wrap;overflow-wrap:anywhere;margin:0}.exam-station{display:flex;min-height:660px}.exam-paused{position:sticky;top:0;z-index:20;border:1px solid #c48932;background:#fff6df;padding:20px;margin-bottom:14px}.exam-paused h2{font-size:18px;margin:0 0 8px}.exam-paused p{line-height:1.8}.exam-paused .el-button{margin:6px 12px 0 0}.exam-notice{background:#fff0e9;border:1px solid #dba17e;padding:14px;line-height:1.8}.exam-finished,.exam-loading{max-width:1050px;margin:30px auto;background:white;padding:30px;border:1px solid #dfe7ef;border-top:4px solid #17815b}.exam-finished h1{font-size:24px;line-height:1.6}.exam-finished h2{font-size:19px}.exam-finished p{line-height:1.8}.exam-finished .op-actions-group{margin:24px 0}.exam-loading a{margin-left:20px}button:focus-visible,a:focus-visible{outline:3px solid #0075b7;outline-offset:3px}@media(max-width:650px){.exam-shell{padding:10px}.exam-header{padding:14px;gap:14px;flex-wrap:wrap}.exam-header>div:first-child{flex-basis:100%}.exam-header h1{font-size:20px}.exam-countdown{text-align:left}.exam-header>.el-button{margin-left:auto}.exam-finished,.exam-loading{padding:20px 16px}.exam-finished h1{font-size:21px}.exam-station{min-height:640px}}
</style>
