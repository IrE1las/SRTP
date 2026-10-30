<template>
  <section class="op-page exam-page" v-loading="loading"><router-link class="op-back" :to="listPath">← 返回考试管理</router-link>
    <header class="exam-masthead"><div><p class="exam-kicker">标准站 · 考试安排</p><h1>{{ current?.status === 'published' ? '考试详情' : current ? '编辑考试草稿' : '新建考试' }}</h1><p class="op-muted">时间统一按北京时间填写和显示。</p></div><span v-if="current" class="exam-badge" :class="current.status">{{ examStates[current.status] }}</span></header>
    <el-alert v-if="notice" :title="notice" type="error" :closable="false" role="alert" />
    <template v-if="!loading && ready">
      <div class="exam-form-layout"><div class="exam-form-body">
        <el-form label-position="top" :disabled="working || published" @submit.prevent="publish">
          <section class="exam-form-section"><h2>考试设置</h2>
            <dl v-if="published" class="exam-facts"><div class="wide"><dt>考试名称</dt><dd>{{ current.name }}</dd></div><div class="wide"><dt>目标班级</dt><dd>{{ current.classes.join('、') }}</dd></div><div><dt>开放时间（北京时间）</dt><dd>{{ beijingTime(current.opens_at) }}</dd></div><div><dt>截止时间（北京时间）</dt><dd>{{ beijingTime(current.closes_at) }}</dd></div><div><dt>答题时长</dt><dd>{{ current.duration_minutes }} 分钟</dd></div></dl>
            <template v-else><el-form-item label="考试名称" for="exam-name" :error="errors.name"><el-input id="exam-name" v-model="form.name" maxlength="200" /></el-form-item>
            <el-form-item label="目标班级" for="exam-classes" :error="errors.classes"><el-select id="exam-classes" v-model="form.classes" multiple filterable placeholder="从现有学生班级选择"><el-option v-for="item in classOptions" :key="item.name" :label="`${item.name}（${item.student_count ?? '原名单'}）`" :value="item.name" /></el-select></el-form-item>
            <div class="exam-dates"><el-form-item label="开放时间（北京时间）" for="exam-opens-at" :error="errors.opens_at"><input id="exam-opens-at" name="exam-opens-at" v-model="form.opens_at" class="exam-date-input" type="datetime-local" :disabled="working || published" /></el-form-item><el-form-item label="截止时间（北京时间）" for="exam-closes-at" :error="errors.closes_at"><input id="exam-closes-at" name="exam-closes-at" v-model="form.closes_at" class="exam-date-input" type="datetime-local" :disabled="working || published" /></el-form-item></div>
            <el-form-item label="答题时长（分钟）" for="exam-duration-minutes" :error="errors.duration_minutes"><el-input-number id="exam-duration-minutes" v-model="form.duration_minutes" :min="1" :max="10080" :precision="0" /></el-form-item>
            </template><p class="op-help">个人结束时间取考试截止与本人开始加答题时长的较早者。发布后改动需复制为新考试。</p>
          </section>
          <section id="exam-version-id" tabindex="-1" class="exam-form-section"><h2>操作题版本</h2><p v-if="errors.version_id" class="exam-field-error" role="alert">{{ errors.version_id }}</p>
            <p v-if="selectedTitle" class="exam-selected">已选：{{ selectedTitle }}</p><p v-else class="op-muted">尚未选择已发布操作题版本。</p>
            <template v-if="!published"><div class="op-search"><el-input v-model="search" placeholder="按题目标题搜索" clearable @keydown.enter.prevent="loadVersions(1)" /><el-button @click="loadVersions(1)">搜索</el-button></div>
              <el-radio-group v-model="form.version_id" class="exam-version-options" aria-label="已发布操作题版本"><el-radio v-for="item in versions.items" :key="item.version_id" :value="item.version_id" @change="selectedTitle = `${item.title} · v${item.number}`">{{ item.title }} · v{{ item.number }}</el-radio></el-radio-group>
              <p v-if="!versions.items.length" class="op-help">暂无可选版本，请先在操作题库录制并发布操作题。</p><ListPager :page="versionPage" :total="versions.total" @change="loadVersions" />
            </template>
            <template v-if="current?.question"><h3>{{ current.question.title }} · v{{ current.question.number }}</h3><p class="op-preserve">{{ current.question.prompt }}</p><details><summary>查看本场考试的标准操作日志</summary><OperationLog :events="current.question.standard_log || []" /></details></template>
          </section>
          <div v-if="!published" class="exam-action-bar"><p role="status">{{ dirty ? '有未保存的修改，可直接发布' : current ? '配置已保存，可直接发布' : '填写完整后可直接发布考试' }}</p><div class="exam-tools"><el-button :loading="working" @click="save">保存草稿</el-button><el-button type="primary" native-type="submit" :loading="working">发布考试</el-button></div></div>
        </el-form>
        <div v-if="current" class="exam-secondary-actions"><el-button :disabled="working || dirty" @click="clone">复制为新考试</el-button><el-button v-if="published" :disabled="working || current.attempt_count > 0" @click="withdraw">撤回为草稿</el-button><el-button :disabled="working || dirty" @click="load">刷新详情</el-button></div>
      </div>
      <aside class="exam-review-card"><h2>{{ published ? '已发布的考试安排' : '发布前核对' }}</h2><dl class="exam-facts"><div><dt>所选操作题</dt><dd>{{ selectedTitle || '尚未选择' }}</dd></div><div><dt>目标班级</dt><dd>{{ form.classes.join('、') || '尚未选择' }}</dd></div><div><dt>答题时长</dt><dd>{{ form.duration_minutes ? form.duration_minutes + ' 分钟' : '尚未设置' }}</dd></div><template v-if="published"><div><dt>本场考试名单</dt><dd>{{ current.participant_count }} 人</dd></div><div><dt>已开始作答</dt><dd>{{ current.attempt_count }} 人</dd></div></template></dl><p>发布后，本场考试使用发布时的学生名单、题目和初始条件；之后改班或改题不会影响本场考试。每名学生只有一次正式机会。</p><p>{{ published ? '需要变更安排时，复制为新考试。已有学生开始的考试不能撤回。' : '填写完整后即可发布；暂未填完也可以保存草稿。' }}</p></aside></div>
      <section v-if="published" class="exam-form-section exam-record-section"><h2>本场考试名单</h2><el-table :data="participants.items" empty-text="暂无名单"><el-table-column prop="class_name" label="班级" /><el-table-column prop="student_id" label="学号" /><el-table-column prop="real_name" label="姓名" /></el-table><ListPager :page="participantPage" :total="participants.total" @change="loadParticipants" /></section>
      <section v-if="published" class="exam-form-section"><h2>考试答卷</h2><el-table :data="attempts.items" empty-text="尚无学生开始"><el-table-column prop="identity.class_name" label="班级" min-width="130" /><el-table-column prop="identity.student_id" label="学号" min-width="140" /><el-table-column prop="identity.real_name" label="姓名" min-width="100" /><el-table-column label="状态" min-width="100"><template #default="{row}">{{ examStates[row.status] }}</template></el-table-column><el-table-column prop="finish_reason_text" label="交卷原因" min-width="160" /><el-table-column label="成绩状态" min-width="160"><template #default="{row}">{{ gradeStates[row.grade?.status] || '待批阅' }}</template></el-table-column><el-table-column label="操作" width="130"><template #default="{row}"><router-link class="exam-table-link" :to="`/exams/manage/attempts/${row.session_id}`">查看与批阅</router-link></template></el-table-column></el-table><ListPager :page="attemptPage" :total="attempts.total" @change="loadAttempts" /></section>
    </template>
    <el-button v-if="!ready && !loading" @click="load">重新加载</el-button>
  </section>
</template>
<script setup>
import '@/features/exams/exam.css'
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { useUserStore } from '@/store/user'
import ListPager from '@/components/ListPager.vue'
import OperationLog from '@/features/operationQuestions/OperationLog.vue'
import { getOperationClasses } from '@/api/operations'
import { gradeStates } from '@/domain/examGrades'
import { getExam, createExam, editExam, publishExam, withdrawExam, copyExam, examVersions, examParticipants, examAttempts } from '@/api/exams'
import { examPayload, beijingTime, beijingInput, examError, examStates, examFormErrors } from '@/domain/exams'
const route = useRoute(), router = useRouter(), user = useUserStore(), listPath = computed(() => user.role === 'admin' ? '/exams/manage' : '/teacher/exams')
const current = ref(null), loading = ref(false), ready = ref(false), working = ref(false), notice = ref(''), availableClasses = ref([]), selectedTitle = ref('')
const errors = ref({})
const form = reactive({ name:'', classes:[], version_id:null, opens_at:'', closes_at:'', duration_minutes:null })
const saved = ref(JSON.stringify(examPayload(form))), dirty = computed(() => JSON.stringify(examPayload(form)) !== saved.value), published = computed(() => current.value?.status === 'published')
const classOptions = computed(() => [...availableClasses.value, ...form.classes.filter(name => !availableClasses.value.some(item => item.name === name)).map(name => ({name}))])
const versions = ref({items:[],total:0}), search = ref(''), versionPage = ref(1), participants = ref({items:[],total:0}), participantPage = ref(1), attempts = ref({items:[],total:0}), attemptPage = ref(1)
let loadSerial = 0
function fill(data) {
  const previousVersion = form.version_id, previousTitle = selectedTitle.value
  current.value = data; errors.value = {}
  Object.assign(form, data ? { name:data.name || '', classes:[...data.classes], version_id:data.version_id, opens_at:beijingInput(data.opens_at), closes_at:beijingInput(data.closes_at), duration_minutes:data.duration_minutes } : { name:'', classes:[], version_id:null, opens_at:'', closes_at:'', duration_minutes:null })
  saved.value = JSON.stringify(examPayload(form)); selectedTitle.value = data?.question ? `${data.question.title} · v${data.question.number}` : data?.version_id ? (data.version_id === previousVersion && previousTitle ? previousTitle : '已选择的题目版本') : ''
}
async function loadVersions(page = 1) { try { versions.value = await examVersions(page, search.value); versionPage.value = page; const selected = versions.value.items.find(v => v.version_id === form.version_id); if (selected) selectedTitle.value = `${selected.title} · v${selected.number}` } catch (error) { notice.value = examError(error) } }
async function loadParticipants(page = 1) { participants.value = await examParticipants(current.value.id, page); participantPage.value = page }
async function loadAttempts(page = 1) { attempts.value = await examAttempts(current.value.id, page); attemptPage.value = page }
async function load() {
  const serial = ++loadSerial; loading.value = true; ready.value = false; notice.value = ''
  try {
    const [classes, data] = await Promise.all([getOperationClasses(), route.params.examId ? getExam(route.params.examId) : Promise.resolve(null)])
    if (serial !== loadSerial) return
    availableClasses.value = classes.items; fill(data)
    if (published.value) await Promise.all([loadParticipants(), loadAttempts()]); else await loadVersions()
    ready.value = true
  } catch (error) { notice.value = examError(error) }
  finally { if (serial === loadSerial) loading.value = false }
}
async function persistDraft() {
  const data = current.value ? await editExam(current.value.id, { ...examPayload(form), revision: current.value.revision }) : await createExam(examPayload(form))
  fill(data)
  return data
}
async function save() {
  if (working.value || published.value) return
  working.value = true; notice.value = ''; errors.value = {}
  try { const data = await persistDraft(); await router.replace(`/exams/manage/${data.id}`) }
  catch (error) { notice.value = examError(error) } finally { working.value = false }
}
async function publish() {
  if (working.value || published.value) return
  errors.value = examFormErrors(form)
  if (Object.keys(errors.value).length) {
    notice.value = '请补全或修正标出的项目。'
    await nextTick()
    document.getElementById('exam-' + Object.keys(errors.value)[0].replaceAll('_', '-'))?.focus()
    return
  }
  working.value = true
  try { await ElMessageBox.confirm('发布后，本场考试使用现在的学生名单和题目内容，不能直接修改。确认发布？', '发布考试', {confirmButtonText:'发布考试',cancelButtonText:'继续核对'}) } catch { working.value = false; return }
  working.value = true; notice.value = ''
  try {
    const draft = !current.value || dirty.value ? await persistDraft() : current.value
    fill(await publishExam(draft.id, draft.revision))
    await Promise.all([loadParticipants(), loadAttempts()])
    await router.replace(`/exams/manage/${current.value.id}`)
  } catch (error) { notice.value = examError(error) } finally { working.value = false }
}
async function withdraw() {
  try { await ElMessageBox.confirm('仅无人开始的考试可以撤回。撤回后不再向原名单开放，再发布时重新确定学生名单。', '撤回考试', {confirmButtonText:'撤回为草稿',cancelButtonText:'取消'}) } catch { return }
  working.value = true
  try { fill(await withdrawExam(current.value.id, current.value.revision)); await loadVersions() } catch (error) { notice.value = examError(error) } finally { working.value = false }
}
async function clone() { working.value = true; try { const data = await copyExam(current.value.id); fill(data); await router.push(`/exams/manage/${data.id}`) } catch (error) { notice.value = examError(error) } finally { working.value = false } }
async function leave() { if (!dirty.value) return true; try { await ElMessageBox.confirm('考试设置有未保存修改，离开后将丢失。', '离开编辑', {confirmButtonText:'放弃修改',cancelButtonText:'继续编辑'}); return true } catch { return false } }
function unload(event) { if (dirty.value) { event.preventDefault(); event.returnValue = '' } }
onBeforeRouteLeave(leave); onBeforeRouteUpdate(leave)
watch(() => route.params.examId, load, { immediate: true })
onMounted(() => window.addEventListener('beforeunload', unload)); onBeforeUnmount(() => { loadSerial++; window.removeEventListener('beforeunload', unload) })
</script>
<style scoped>
.exam-dates{display:grid;grid-template-columns:1fr 1fr;gap:20px}.exam-date-input{width:100%;font:inherit;color:#19334d;background:#fff;padding:10px;border:1px solid #c8d6e3;border-radius:5px}.exam-date-input:focus-visible{outline:2px solid #0075b7}.exam-date-input:disabled{background:#f5f7fa;color:#606e7d}.exam-version-options{display:flex;align-items:stretch;flex-direction:column;margin-top:18px;max-width:100%;gap:6px}.exam-version-options .el-radio{margin:0;height:auto;min-height:40px}.exam-version-options :deep(.el-radio__label){white-space:normal;line-height:1.8;overflow-wrap:anywhere}.exam-selected{padding:12px;background:#edf4fa;margin-bottom:18px!important}details{margin-top:20px}summary{cursor:pointer;color:#0075b7;font-weight:600}@media(max-width:650px){.exam-dates{grid-template-columns:1fr;gap:0}}
</style>
