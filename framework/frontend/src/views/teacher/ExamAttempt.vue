<template>
  <section class="op-page exam-page" v-loading="loading"><router-link class="op-back" :to="data ? `/exams/manage/${data.exam_id}` : '/exams/manage'">← 返回考试详情</router-link><header class="exam-masthead"><div><p class="exam-kicker">标准站 · 答卷记录</p><h1>考试操作记录</h1><p>核对实际操作、交卷原因与全屏事件。</p></div><el-button @click="load">刷新记录</el-button></header><el-alert v-if="notice" :title="notice" type="error" :closable="false" />
    <template v-if="data"><section class="exam-form-section"><div class="exam-section-head"><h2>{{ data.name }}</h2><span class="exam-badge" :class="data.status">{{ examStates[data.status] }}</span></div><dl class="exam-facts"><div class="wide"><dt>学生</dt><dd>{{ data.identity.class_name }} · {{ data.identity.student_id }} · {{ data.identity.real_name }}</dd></div><div><dt>开始时间（北京时间）</dt><dd>{{ beijingTime(data.started_at) }}</dd></div><div><dt>个人截止</dt><dd>{{ beijingTime(data.deadline) }}</dd></div><div><dt>交卷原因</dt><dd>{{ data.finish_reason_text || 'null' }}</dd></div><div><dt>交卷时间</dt><dd>{{ beijingTime(data.submitted_at) }}</dd></div><div><dt>退出全屏</dt><dd>{{ data.exit_count }} 次</dd></div></dl><div class="exam-secondary-actions" style="margin-top:22px;margin-bottom:0"><el-button @click="download">下载考试日志</el-button></div></section>
      <section class="exam-form-section exam-log-section"><h2>{{ data.question.title }} · v{{ data.question.number }}</h2><p class="op-preserve">{{ data.question.prompt }}</p></section>
      <section class="exam-form-section exam-log-section"><h2>学生操作</h2><OperationLog :events="data.console?.events || []" /></section><section class="exam-form-section exam-log-section"><h2>本场考试的标准操作</h2><OperationLog :events="data.question.standard_log || []" /></section>
      <section class="exam-form-section exam-log-section"><h2>全屏事件</h2><el-table :data="controlPage" empty-text="暂无退出或恢复记录"><el-table-column label="事件" width="130"><template #default="{row}">{{ row.kind === 'exit' ? '退出全屏' : '恢复全屏' }}</template></el-table-column><el-table-column label="发生时间（北京时间）" min-width="190"><template #default="{row}">{{ beijingTime(row.effective_at) }}</template></el-table-column><el-table-column label="处理" width="150"><template #default="{row}">{{ row.applied ? '已应用' : '状态未改变' }}</template></el-table-column></el-table><ListPager :page="page" :total="data.control_events.length" @change="page = $event" /></section>
    </template>
  </section>
</template>
<script setup>
import '@/features/exams/exam.css'
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import OperationLog from '@/features/operationQuestions/OperationLog.vue'
import ListPager from '@/components/ListPager.vue'
import { getExamAttempt, downloadExam } from '@/api/exams'
import { beijingTime, examError, examStates } from '@/domain/exams'
const route = useRoute(), data = ref(null), loading = ref(false), notice = ref(''), page = ref(1)
const controlPage = computed(() => data.value?.control_events.slice((page.value - 1) * 6, page.value * 6) || [])
async function load() { loading.value = true; notice.value = ''; try { data.value = await getExamAttempt(route.params.attemptId) } catch (error) { notice.value = examError(error) } finally { loading.value = false } }
async function download() { try { await downloadExam(route.params.attemptId) } catch (error) { notice.value = examError(error) } }
watch(() => route.params.attemptId, load, { immediate: true })
</script>
