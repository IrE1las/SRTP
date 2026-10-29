<template>
  <section class="learning-result" aria-label="操作学习结果">
    <div class="result-columns">
      <section><h2>ai分析日志</h2>
        <p class="result-outcome" :class="attempt.outcome?.status">{{ outcomeText(attempt.outcome) }}</p>
        <p v-if="attempt.outcome?.status === 'error'">分数：null</p>
        <p v-if="attempt.outcome?.first_difference">首个差异：第 {{ attempt.outcome.first_difference.sequence }} 次点击</p>
        <dl v-if="attempt.outcome?.first_difference" class="difference"><dt>标准操作</dt><dd>{{ describe(attempt.outcome.first_difference.expected) }}</dd><dt>实际操作</dt><dd>{{ describe(attempt.outcome.first_difference.actual) }}</dd></dl>
        <div class="result-logs"><details open><summary>学生日志（{{ attempt.console?.events.length || 0 }}）</summary><OperationLog :events="attempt.console?.events || []" /></details>
        <details><summary>标准日志（{{ attempt.question.standard_log?.length || 0 }}）</summary><OperationLog :events="attempt.question.standard_log || []" /></details></div>
      </section>
      <section><h2>ai评价讲解</h2><p class="ai-state" role="status">{{ explanationStatus(attempt.ai_status) }}</p>
        <p class="op-preserve">{{ attempt.ai_text ?? 'null' }}</p>
        <el-button :loading="explaining" @click="$emit('explain')">{{ attempt.ai_text ? '重新生成讲解' : '生成 / 重试讲解' }}</el-button>
        <section v-if="attempt.review?.comment || attempt.review?.confirmed" class="teacher-comment"><h3>教师评语</h3><p>{{ attempt.review.confirmed ? '已确认查看' : '待确认' }}</p><p class="op-preserve">{{ attempt.review.comment ?? 'null' }}</p></section>
      </section>
    </div>
  </section>
</template>
<script setup>
import OperationLog from './OperationLog.vue'
import { outcomeText, explanationStatus } from '@/domain/operationLearning'
import { buttonLabel } from '@/domain/operationPresentation'
defineProps({ attempt: { type: Object, required: true }, explaining: Boolean })
defineEmits(['explain'])
function describe(event) {
  if (!event) return '无此步骤'
  const label = buttonLabel(event.button_id)
  const parameters = event.parameters || {}
  const kind = ({ switch: '道岔', signal: '信号机', section: '区段', block: '区间按钮' })[parameters.target_kind]
  return [label, event.target_id, kind, parameters.signal ? '信号机 ' + parameters.signal : ''].filter(Boolean).join(' · ')
}
</script>
<style scoped>
.result-columns{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(260px,1fr);gap:28px}.result-columns>section{min-width:0}.result-columns h2{font-size:19px;margin:0 0 14px}.result-columns p{line-height:1.8}.result-outcome{font-size:24px;font-weight:600}.result-outcome.correct{color:#236a43}.result-outcome.error{color:#a73b2d}.result-logs{display:grid;gap:14px}.result-logs summary{cursor:pointer;padding:10px 0;font-weight:600}.difference{display:grid;grid-template-columns:88px 1fr;gap:8px;margin:16px 0;font-size:14px}.difference dd{margin:0;overflow-wrap:anywhere}.ai-state{color:#586f82}.teacher-comment{border-top:1px solid #dce5ef;margin-top:24px;padding-top:12px}.teacher-comment h3{font-size:16px}@media(max-width:900px){.result-columns{grid-template-columns:minmax(0,1fr)}}
</style>
