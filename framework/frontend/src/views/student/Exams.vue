<template>
  <section class="op-page exam-page" v-loading="loading">
    <header class="exam-masthead"><div><p class="exam-kicker">标准站 · 操作考试</p><h1>考试界面</h1><p>查看考试安排，准备就绪后全屏参加。</p></div><div class="exam-tools"><router-link to="/student/exams/history">历史考试 →</router-link><el-button @click="load">刷新考试</el-button></div></header>
    <el-alert v-if="notice" :title="notice" type="error" :closable="false" role="alert" />
    <section aria-labelledby="exam-list-title"><div class="exam-section-head"><div><h2 id="exam-list-title">考试安排</h2><p>全部考试 · 北京时间</p></div><el-popover placement="bottom-end" trigger="click" :width="290"><template #reference><el-button text size="small">考试须知</el-button></template><p class="exam-rules-note">每场一次机会，允许全屏后开始作答。首次退出须在60秒内恢复，第二次退出立即交卷。刷新与断线不停计时。</p></el-popover></div>
      <div v-if="ready && !items.length" class="exam-empty"><h3>暂无考试安排</h3><p>教师发布后，考试会显示在这里。</p><router-link to="/student/exams/history">查看历史考试 →</router-link></div>
      <article v-for="exam in items" :key="exam.id" class="exam-sitting">
        <div><div class="exam-sitting-title"><h3>{{ exam.name }}</h3><span class="exam-badge" :class="exam.state">{{ examStates[exam.state] }}</span></div><dl class="exam-schedule"><div><dt>开放时间</dt><dd>{{ beijingTime(exam.opens_at) }}</dd></div><div><dt>截止时间</dt><dd>{{ beijingTime(exam.closes_at) }}</dd></div></dl></div>
        <div class="exam-entry"><p><strong>{{ exam.duration_minutes }}</strong>分钟</p><el-button :type="['open','active'].includes(exam.state) ? 'primary' : 'default'" :disabled="working !== null || !['open','active'].includes(exam.state)" :loading="working === exam.id" @click="participate(exam)">{{ examAction(exam) }}</el-button><router-link v-if="exam.state === 'submitted' && exam.attempt" :to="`/student/exams/attempts/${exam.attempt.session_id}`">查看本人记录</router-link></div>
      </article><ListPager :page="page" :total="total" @change="changePage" />
    </section>
  </section>
</template>
<script setup>
import '@/features/exams/exam.css'
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ListPager from '@/components/ListPager.vue'
import { beginExam, listExams } from '@/api/exams'
import { beijingTime, examStates, examError, enterExam, examAction } from '@/domain/exams'
const route = useRoute(), router = useRouter(), loading = ref(false), ready = ref(false), notice = ref(''), working = ref(null)
const items = ref([]), total = ref(0), page = ref(Math.max(1, Number(route.query.page) || 1))
let timer, serial = 0
async function load() {
  const token = ++serial; loading.value = true
  try { const data = await listExams(page.value); if (token !== serial) return; items.value = data.items; total.value = data.total; ready.value = true }
  catch (error) { notice.value = examError(error, '考试加载失败，请刷新。') }
  finally { if (token === serial) loading.value = false }
}
async function changePage(value) { page.value = value; await router.replace({ query: { page: value } }); await load() }
async function participate(exam) {
  if (working.value !== null || !['open','active'].includes(exam.state)) return
  working.value = exam.id; notice.value = ''
  try {
    const result = await enterExam(async () => { if (!document.fullscreenElement) await document.documentElement.requestFullscreen() }, () => beginExam(exam.id))
    await router.push(`/student/exams/attempts/${result.session_id}`)
  } catch (error) {
    notice.value = examError(error, '未能进入全屏或开始考试。尚未确认开始，请刷新考试状态后重试。')
    if (document.fullscreenElement) await document.exitFullscreen().catch(() => {})
  } finally { working.value = null }
}
onMounted(() => { load(); timer = setInterval(() => { if (!loading.value && working.value === null) load() }, 15000) })
onBeforeUnmount(() => { serial++; clearInterval(timer) })
</script>
