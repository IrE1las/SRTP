<template>
  <section class="op-page learning-page" :aria-busy="loading">
    <header class="op-heading"><div><router-link :to="back">返回</router-link><h1>{{ attempt?.question.title || '操作答题' }}</h1></div>
      <div v-if="attempt" class="op-actions-group"><span>{{ attemptStatus(attempt.status) }} · v{{ attempt.question.number }}</span>
        <el-button :loading="working" @click="restart">重新开始</el-button>
        <el-button v-if="attempt.status === 'active'" type="primary" :loading="working" @click="submit">提交</el-button>
        <el-button v-else-if="attempt.status === 'submitted'" @click="download">下载日志</el-button>
      </div>
    </header>
    <el-alert v-if="notice" :title="notice" type="error" :closable="false" role="alert" />
    <el-button v-if="!attempt && !loading" @click="load">重新加载</el-button>
    <template v-if="attempt">
      <div class="learning-work-area">
      <details class="op-panel task-details" :open="attempt.status === 'active'"><summary>题干与初始条件</summary><p class="op-preserve">{{ attempt.question.prompt }}</p><p>区间许可：{{ attempt.question.initial.interval_available ? '具备' : '不具备' }} · 预置占用：{{ attempt.question.initial.occupied_sections.join('、') || '全部空闲' }}</p></details>
      <div class="learning-station"><OperationConsole :key="attempt.session_id" ref="consoleRef" :session-id="attempt.session_id" :api="learningConsoleApi" :read-only="working || attempt.status !== 'active'" @update="consoleUpdate" /></div>
      <div v-if="attempt.status === 'submitted'" class="learning-result-dock">
        <button ref="resultToggle" class="result-toggle" type="button" :aria-expanded="resultOpen" aria-controls="learning-results" @click="resultOpen = !resultOpen">{{ resultOpen ? '收起结果' : '查看结果' }} · {{ outcomeText(attempt.outcome) }}</button>
        <Transition name="result-rise"><section v-show="resultOpen" id="learning-results" class="result-body" tabindex="0" aria-label="操作结果，可滚动查看"><LearningResult :attempt="attempt" :explaining="explaining" @explain="explain" /><el-button :loading="loading" @click="load">刷新结果与教师评语</el-button></section></Transition>
      </div>
      </div>
    </template>
  </section>
</template>
<script setup>
import { computed, ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter, onBeforeRouteLeave, onBeforeRouteUpdate } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import OperationConsole from '@/features/simulationConsole/OperationConsole.vue'
import LearningResult from '@/features/operationQuestions/LearningResult.vue'
import { beginLearning, getLearning, submitLearning, explainLearning, downloadLearning, learningConsoleApi } from '@/api/operationLearning'
import { attemptStatus, outcomeText, learningError } from '@/domain/operationLearning'
import { pageNumber } from '@/domain/pagination'
import '@/features/operationQuestions/operation.css'
const route = useRoute(), router = useRouter()
const attempt = ref(null), loading = ref(false), working = ref(false), explaining = ref(false), notice = ref('')
const consoleRef = ref(null), resultOpen = ref(false), resultToggle = ref(null)
const back = computed(() => route.query.historyPage ? { path: '/student/learn/operations/history', query: { page: String(pageNumber(route.query.historyPage)) } } : { path: '/student/learn/operations', query: pageNumber(route.query.backPage) > 1 ? { page: String(pageNumber(route.query.backPage)) } : {} })
let token = 0, leavingAfterRestart = false
async function load() {
  const ownToken = ++token
  loading.value = true; notice.value = ''
  try { const data = await getLearning(route.params.attemptId); if (ownToken === token) { attempt.value = data; resultOpen.value = data.status === 'submitted' } }
  catch (e) { if (ownToken === token) notice.value = learningError(e) }
  finally { if (ownToken === token) loading.value = false }
}
function consoleUpdate(data) { if (attempt.value && data.session_id === attempt.value.session_id) { attempt.value.console = data; attempt.value.status = data.status } }
async function submit() {
  if (working.value || attempt.value?.status !== 'active') return
  working.value = true; notice.value = ''
  try {
    await consoleRef.value?.flush()
    attempt.value = await submitLearning(attempt.value.session_id)
    consoleRef.value?.sync(attempt.value.console)
    resultOpen.value = true
  } catch (e) { notice.value = learningError(e) }
  finally { working.value = false }
  if (attempt.value?.status === 'submitted' && attempt.value.ai_status === 'not_requested') await explain()
}
async function restart() {
  if (working.value || !attempt.value) return
  try { await ElMessageBox.confirm('将创建新的作答；当前未提交记录会标记为已放弃，所有旧记录保留。', '重新开始', { confirmButtonText: '重新开始', cancelButtonText: '取消' }) } catch { return }
  working.value = true; notice.value = ''
  try {
    await consoleRef.value?.flush()
    const next = await beginLearning(attempt.value.question_id, attempt.value.session_id)
    leavingAfterRestart = true
    await router.replace({ path: '/student/learn/operations/attempts/' + next.session_id, query: route.query })
  } catch (e) { notice.value = learningError(e) }
  finally { working.value = false; leavingAfterRestart = false }
}
async function explain() {
  if (explaining.value || attempt.value?.status !== 'submitted') return
  explaining.value = true; notice.value = ''
  const sid = attempt.value.session_id
  try { const data = await explainLearning(sid); if (attempt.value?.session_id === sid) attempt.value = data }
  catch (e) { notice.value = learningError(e, '讲解请求尚未确认，请刷新结果或重试。') }
  finally { explaining.value = false }
}
async function download() { try { await downloadLearning(attempt.value.session_id) } catch (e) { notice.value = learningError(e) } }
async function allowLeave() {
  if (leavingAfterRestart) return true
  if (working.value) return false
  try { await consoleRef.value?.flush(); return true } catch (e) { notice.value = learningError(e); return false }
}
onBeforeRouteLeave(allowLeave)
onBeforeRouteUpdate(allowLeave)
function beforeUnload(event) { if (consoleRef.value?.hasUnconfirmed) { event.preventDefault(); event.returnValue = '' } }
onMounted(() => window.addEventListener('beforeunload', beforeUnload))
onBeforeUnmount(() => { token++; window.removeEventListener('beforeunload', beforeUnload) })
watch(() => route.params.attemptId, load, { immediate: true })
</script>
<style scoped>
.learning-page{min-width:0}.learning-work-area{position:relative;min-width:0}.learning-page h1{margin-top:12px}.task-details{margin-bottom:16px}.task-details summary{cursor:pointer;font-weight:600}.task-details p{line-height:1.9}.learning-station{display:flex;min-height:660px;min-width:0}.learning-result-dock{position:sticky;bottom:0;z-index:10;margin-top:18px;border:1px solid #a9c4d9;background:#fff;box-shadow:0 -4px 16px #18344b12;max-width:100%;border-radius:7px 7px 0 0}.result-toggle{display:block;width:100%;text-align:left;background:#093278;color:white;border:0;padding:14px 20px;font:600 16px 'Microsoft YaHei',sans-serif;cursor:pointer}.result-body{padding:22px;max-height:65dvh;overflow:auto;overscroll-behavior:contain}.result-body:focus-visible{outline:3px solid #0075b7;outline-offset:-3px}.result-rise-enter-active,.result-rise-leave-active{transition:transform .18s ease,opacity .18s ease}.result-rise-enter-from,.result-rise-leave-to{transform:translateY(18px);opacity:0}@media(max-width:650px){.learning-page .op-heading{align-items:flex-start}.learning-station{min-height:640px}.result-body{padding:16px}.op-actions-group{flex-wrap:wrap}}@media(prefers-reduced-motion:reduce){.result-rise-enter-active,.result-rise-leave-active{transition:none}}
</style>
