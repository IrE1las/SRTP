<template>
  <section class="op-page exam-page" v-loading="loading">
    <router-link class="op-back" :to="data ? `/exams/manage/${data.exam_id}` : '/exams/manage'">← 返回考试详情</router-link>
    <header class="exam-masthead"><div><h1>考试批阅</h1><p v-if="data">{{ data.name }} · {{ data.identity.class_name }} · {{ data.identity.student_id }} · {{ data.identity.real_name }}</p></div><el-button :disabled="working || loading" @click="refresh">刷新记录</el-button></header>
    <el-alert v-if="notice" :title="notice" type="error" :closable="false" role="alert" />
    <p v-if="success" class="exam-grade-notice" role="status">{{ success }}</p>
    <div v-if="data" class="exam-grading-layout">
      <div class="exam-grade-evidence">
        <section class="exam-form-section">
          <div class="exam-section-head"><h2>答卷记录</h2><span class="exam-badge" :class="data.status">{{ examStates[data.status] }}</span></div>
          <dl class="exam-facts"><div><dt>开始时间（北京时间）</dt><dd>{{ beijingTime(data.started_at) }}</dd></div><div><dt>个人截止</dt><dd>{{ beijingTime(data.deadline) }}</dd></div><div><dt>交卷原因</dt><dd>{{ data.finish_reason_text || '尚未交卷' }}</dd></div><div><dt>交卷时间</dt><dd>{{ beijingTime(data.submitted_at) }}</dd></div><div><dt>退出全屏</dt><dd>{{ data.exit_count }} 次</dd></div></dl>
          <div class="exam-grade-tools"><el-button @click="download">下载考试日志</el-button></div>
        </section>
        <section class="exam-form-section"><h2>{{ data.question.title }} · v{{ data.question.number }}</h2><p class="op-preserve">{{ data.question.prompt }}</p></section>
        <section class="exam-form-section"><h2>学生操作</h2><OperationLog :events="data.console?.events || []" /></section>
        <section class="exam-form-section"><h2>本场考试的标准操作</h2><OperationLog :events="data.question.standard_log || []" /></section>
        <section class="exam-form-section"><details><summary>全屏事件（{{ data.control_events.length }}）</summary>
          <el-table :data="controlPage" empty-text="暂无退出或恢复记录"><el-table-column label="事件" width="130"><template #default="{row}">{{ row.kind === 'exit' ? '退出全屏' : '恢复全屏' }}</template></el-table-column><el-table-column label="发生时间（北京时间）" min-width="190"><template #default="{row}">{{ beijingTime(row.effective_at) }}</template></el-table-column><el-table-column label="处理" width="130"><template #default="{row}">{{ row.applied ? '已应用' : '状态未改变' }}</template></el-table-column></el-table>
          <ListPager :page="page" :total="data.control_events.length" @change="page = $event" />
        </details></section>
        <section v-if="grade.publications?.length" class="exam-form-section"><h2>成绩发布记录</h2>
          <el-table :data="publicationPage"><el-table-column prop="version" label="版本" width="70" /><el-table-column prop="score" label="成绩" width="80" /><el-table-column prop="comment" label="已发布评语" min-width="150" /><el-table-column prop="publisher_id" label="发布人ID" width="100" /><el-table-column label="发布时间（北京时间）" min-width="190"><template #default="{row}">{{ beijingTime(row.published_at) }}</template></el-table-column></el-table>
          <ListPager :page="releasePage" :total="grade.publications.length" @change="releasePage = $event" />
        </section>
        <section v-if="grade.audit?.length" class="exam-form-section"><details><summary>成绩操作记录（{{ grade.audit.length }}）</summary>
          <el-table :data="auditPage"><el-table-column prop="revision" label="修订" width="70" /><el-table-column label="操作" width="120"><template #default="{row}">{{ gradeActions[row.action] || row.action }}</template></el-table-column><el-table-column prop="actor_id" label="操作者ID" width="110" /><el-table-column prop="snapshot.score" label="成绩" width="80" /><el-table-column prop="snapshot.comment" label="评语" min-width="150" /><el-table-column label="时间（北京时间）" min-width="190"><template #default="{row}">{{ beijingTime(row.occurred_at) }}</template></el-table-column></el-table>
          <ListPager :page="auditNumber" :total="grade.audit.length" @change="auditNumber = $event" />
        </details></section>
      </div>
      <aside class="exam-grade-panel" aria-labelledby="grade-title">
        <div class="exam-section-head"><h2 id="grade-title">人工成绩</h2><span class="exam-grade-status">{{ gradeStates[grade.status] }}</span></div>
        <p v-if="data.status !== 'submitted'" class="op-help">答卷尚未交卷，交卷后可录入成绩。</p>
        <template v-else>
          <div v-if="grade.published" class="exam-grade-release"><span>学生当前可见 · 第 {{ grade.published.version }} 版</span><strong>{{ grade.published.score }}<small> / 100</small></strong><p v-if="grade.published.comment" class="op-preserve">{{ grade.published.comment }}</p><time>{{ beijingTime(grade.published.published_at) }}</time></div>
          <p v-else class="op-help">学生暂时看不到成绩与评语。</p>
          <el-form label-position="top" :disabled="working" @submit.prevent="save">
            <el-form-item label="最终成绩（0—100）" for="exam-grade-score" :error="scoreError"><el-input id="exam-grade-score" v-model="form.score" inputmode="decimal" maxlength="7" autocomplete="off" aria-describedby="exam-grade-hint" /><p id="exam-grade-hint" class="op-help">最多两位小数。</p></el-form-item>
            <el-form-item label="评语（可选）" for="exam-grade-comment"><el-input id="exam-grade-comment" v-model="form.comment" type="textarea" :rows="4" maxlength="4000" show-word-limit /></el-form-item>
            <p class="op-help" role="status">{{ dirty ? '当前输入尚未保存，可保存草稿或直接发布。' : grade.status === 'published' ? '本版已发布；修改成绩或评语后可重新发布。' : '核对成绩后点击发布，学生即可查看；也可先保存草稿。' }}</p>
            <div class="exam-grade-buttons"><el-button native-type="submit" :disabled="!!scoreError || !dirty" :loading="working">保存草稿</el-button><el-button type="primary" :disabled="!hasScore || (!dirty && grade.status === 'published')" :loading="working" @click="publish">发布成绩</el-button></div>
          </el-form>
        </template>
      </aside>
    </div>
    <el-button v-if="!data && !loading" @click="load">重新加载</el-button>
  </section>
</template>
<script setup>
import '@/features/exams/exam.css'
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import OperationLog from '@/features/operationQuestions/OperationLog.vue'
import ListPager from '@/components/ListPager.vue'
import { getExamAttempt, downloadExam, saveExamGrade, publishExamGrade } from '@/api/exams'
import { beijingTime, examError, examStates } from '@/domain/exams'
import { gradeStates, gradeActions, gradeError, gradePayload } from '@/domain/examGrades'

const route = useRoute(), data = ref(null), loading = ref(false), working = ref(false), notice = ref(''), success = ref('')
const page = ref(1), releasePage = ref(1), auditNumber = ref(1), form = reactive({ score: '', comment: '' }), saved = ref(JSON.stringify(form))
const grade = computed(() => data.value?.grade || { revision: 0, status: 'ungraded' })
const dirty = computed(() => JSON.stringify(form) !== saved.value)
const scoreError = computed(() => gradeError(form.score)), hasScore = computed(() => String(form.score).trim() !== '' && !scoreError.value)
const controlPage = computed(() => data.value?.control_events.slice((page.value - 1) * 6, page.value * 6) || [])
const publicationPage = computed(() => grade.value.publications?.slice((releasePage.value - 1) * 6, releasePage.value * 6) || [])
const auditPage = computed(() => grade.value.audit?.slice((auditNumber.value - 1) * 6, auditNumber.value * 6) || [])
let serial = 0
function fill(value) {
  data.value.grade = value
  form.score = value.score == null ? '' : String(value.score)
  form.comment = value.comment || ''
  saved.value = JSON.stringify(form)
}
async function load() {
  const request = ++serial
  loading.value = true; notice.value = ''; success.value = ''
  data.value = null; form.score = ''; form.comment = ''; saved.value = JSON.stringify(form)
  try {
    const value = await getExamAttempt(route.params.attemptId)
    if (request !== serial) return
    data.value = value; fill(value.grade); page.value = releasePage.value = auditNumber.value = 1
  } catch (error) { if (request === serial) notice.value = examError(error) }
  finally { if (request === serial) loading.value = false }
}
async function canDiscard() {
  if (working.value) return false
  if (!dirty.value) return true
  try { await ElMessageBox.confirm('有未保存的成绩或评语，离开后将丢失。', '未保存的修改', { confirmButtonText: '放弃修改', cancelButtonText: '继续编辑' }); return true }
  catch { return false }
}
async function refresh() { if (await canDiscard()) await load() }
async function mutate(action, message) {
  if (working.value || loading.value) return
  working.value = true; notice.value = ''; success.value = ''
  try { fill(await action()); success.value = message; releasePage.value = auditNumber.value = 1 }
  catch (error) { notice.value = examError(error, '成绩操作失败，本地输入已保留。') }
  finally { working.value = false }
}
async function save() {
  if (scoreError.value || !dirty.value) return
  await mutate(() => saveExamGrade(route.params.attemptId, gradePayload(form, grade.value.revision)), '草稿已保存，尚未发布。')
}
async function publish() {
  if (working.value || loading.value || !hasScore.value || (!dirty.value && grade.value.status === 'published')) return
  const payload = gradePayload(form, grade.value.revision)
  working.value = true
  try { await ElMessageBox.confirm(`确认发布 ${payload.score} 分？\n评语：${payload.comment || '无'}\n发布后学生即可查看本版成绩与评语。`, '发布成绩', { confirmButtonText: '发布成绩', cancelButtonText: '继续核对' }) }
  catch { working.value = false; return }
  working.value = false
  await mutate(() => publishExamGrade(route.params.attemptId, payload), '成绩已发布，学生现在可以查看。')
}
async function download() { try { await downloadExam(route.params.attemptId) } catch (error) { notice.value = examError(error) } }
onBeforeRouteLeave(canDiscard)
onBeforeRouteUpdate(canDiscard)
onBeforeUnmount(() => { serial++; window.removeEventListener('beforeunload', beforeUnload) })
function beforeUnload(event) { if (dirty.value || working.value) { event.preventDefault(); event.returnValue = '' } }
window.addEventListener('beforeunload', beforeUnload)
watch(() => route.params.attemptId, load, { immediate: true })
</script>
