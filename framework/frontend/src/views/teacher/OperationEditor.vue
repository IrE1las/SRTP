<template>
  <section class="op-page" v-loading="loading">
    <OperationFlow :back-to="backTo" :step="0" :title="current ? '编辑题目' : '新建操作题'" subtitle="先明确任务和初始条件，再进入站场录制标准答案。"><span v-if="current" class="op-status" :class="current.status">{{ operationStatus(current.status) }} · v{{ current.number }}</span></OperationFlow>
    <el-alert v-if="notice" :title="notice" :type="noticeType" show-icon :closable="false" role="status" />
    <el-alert v-if="current?.status === 'published'" title="保存修改会建立新版本，需要重新录制答案；学生仍可看到当前已发布版本。" type="info" show-icon :closable="false" />
    <el-alert v-if="current?.disabled" title="这道题已停用，题设和记录仅供查看。可回到题库新建题目。" type="info" :closable="false" />
    <div v-if="activeSession" class="op-error-actions"><template v-if="activeSession.owner_id === user.user?.id"><p>请先结束当前录制或预览，再修改题设。</p><router-link :to="destination(current.id, 'record', { session: activeSession.id })">前往操作台 →</router-link></template><template v-else><p>另一位录制人的会话尚未结束，结束后才能修改题设。</p><router-link :to="destination(current.id, 'review')">查看题目记录 →</router-link></template></div>
    <div v-if="!loading && !loadFailed" class="op-form-grid">
      <div class="op-form-body">
        <el-form ref="formRef" :model="form" label-position="top" :disabled="locked || working" @submit.prevent="save(true)">
          <section class="op-panel"><h2>题目内容</h2>
            <el-form-item label="题目标题" prop="title" :error="errors.title"><el-input id="operation-title" v-model="form.title" name="operation-title" maxlength="200" show-word-limit placeholder="例如：D3 至 D7 调车进路练习…" autocomplete="off" /></el-form-item>
            <el-form-item label="任务说明" prop="prompt" :error="errors.prompt"><el-input id="operation-prompt" v-model="form.prompt" name="operation-prompt" type="textarea" :autosize="{ minRows: 5, maxRows: 12 }" maxlength="20000" show-word-limit placeholder="写清学生需要完成的操作及要求…" autocomplete="off" /></el-form-item>
            <el-form-item label="目标班级" prop="classes" :error="errors.classes"><el-select id="operation-classes" v-model="form.classes" multiple filterable :reserve-keyword="false" placeholder="选择目标班级…" no-data-text="暂无学生班级，请先在用户管理完善学生班级" aria-label="目标班级"><el-option v-for="item in classOptions" :key="item.name" :label="item.label" :value="item.name" /></el-select><p class="op-help">班级来自现有学生资料，可多选。发布后仅所选班级可见。</p></el-form-item>
          </section>
          <section class="op-panel"><h2 class="op-section-heading">初始站场条件</h2><p class="op-help" style="margin-bottom:20px">每次录制和预览都会从这些条件开始。</p>
            <el-form-item label="区间许可"><el-radio-group v-model="form.initial.interval_available" aria-label="区间许可"><el-radio :value="true">具备</el-radio><el-radio :value="false">不具备</el-radio></el-radio-group></el-form-item>
            <el-form-item label="预置占用区段"><el-select v-model="form.initial.occupied_sections" multiple filterable clearable placeholder="全部空闲；可选择预置占用的区段…" aria-label="预置占用区段"><el-option v-for="section in station?.sections || []" :key="section.name" :label="section.name" :value="section.name" /></el-select><p class="op-help">未选中的区段保持空闲。修改初始条件后，需要重新录制标准答案。</p></el-form-item>
          </section>
          <div v-if="!locked" class="op-actions"><span class="op-save-state" aria-live="polite">{{ dirty ? '有未保存的修改' : current ? '题设已保存' : '尚未保存' }}</span><div class="op-actions-group"><el-button :loading="working" @click="save(false)">{{ current?.status === 'published' ? '保存为新版本' : '保存草稿' }}</el-button><el-button type="primary" native-type="submit" :loading="working">保存并录制答案 →</el-button></div></div>
        </el-form>
        <div v-if="current" class="op-actions-group"><router-link :to="destination(current.id, 'review')">查看题目与发布状态</router-link></div>
      </div>
      <aside class="op-aside"><h2>出题顺序</h2><p>1. 写明任务，设置班级和初始条件。</p><p>2. 在站场完成一遍标准操作，结束录制并保存答案。</p><p>3. 核对题面和操作日志，再发布给学生。</p><p>题目暂未写完时，可以先保存草稿，稍后继续。</p></aside>
    </div>
    <el-button v-if="loadFailed" @click="load">重新加载题目</el-button>
  </section>
</template>
<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessageBox } from 'element-plus'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/store/user'
import OperationFlow from '@/features/operationQuestions/OperationFlow.vue'
import { initialForm, draftPayload } from '@/domain/operationEvents'
import { operationLocation, operationReturn, operationStatus, operationError, draftErrors } from '@/domain/operationPresentation'
import { getOperation, getOperationStation, getOperationClasses, createOperation, updateOperation } from '@/api/operations'
const route = useRoute(), router = useRouter(), user = useUserStore()
const backTo = computed(() => operationReturn(route.query.back))
function destination(id, step = 'edit', query = {}) { return operationLocation(id, step, backTo.value, query) }
const current = ref(null), station = ref(null), loading = ref(true), loadFailed = ref(false), working = ref(false), notice = ref(''), noticeType = ref('error'), formRef = ref(null)
const availableClasses = ref([])
const classOptions = computed(() => [...availableClasses.value.map(item => ({ name:item.name, label:`${item.name}（${item.student_count} 人）` })), ...form.classes.filter(name => !availableClasses.value.some(item => item.name === name)).map(name => ({ name, label:name + '（原设置，当前无学生）' }))])
const form = reactive(initialForm()), errors = ref({}), saved = ref(JSON.stringify(draftPayload(form, form.classes)))
const payload = computed(() => draftPayload(form, form.classes))
const dirty = computed(() => JSON.stringify(payload.value) !== saved.value)
const activeSession = computed(() => current.value?.sessions?.find(item => item.version_id === current.value.version_id && item.status === 'active'))
const locked = computed(() => !!current.value?.disabled || !!activeSession.value)
let loadToken = 0
function fill(data) {
  current.value = data
  Object.assign(form, data ? { title: data.title || '', prompt: data.prompt || '', classes: [...data.classes], initial: structuredClone(data.initial) } : initialForm())
  saved.value = JSON.stringify(payload.value); errors.value = {}
}
async function load() {
  const token = ++loadToken
  loading.value = true; loadFailed.value = false; notice.value = ''
  try {
    const [reference, data, classes] = await Promise.all([getOperationStation(), route.params.questionId ? getOperation(route.params.questionId) : Promise.resolve(null), getOperationClasses()])
    if (token === loadToken) { station.value = reference; availableClasses.value = classes.items; fill(data) }
  } catch (error) { if (token === loadToken) { loadFailed.value = true; notice.value = operationError(error, '题目加载失败，请重试。'); noticeType.value = 'error' } }
  finally { if (token === loadToken) loading.value = false }
}
async function focusError() { await nextTick(); const key = Object.keys(errors.value)[0]; document.getElementById('operation-' + key)?.focus() }
async function save(continueToRecording = false) {
  if (locked.value || working.value) return
  errors.value = draftErrors(payload.value)
  if (!continueToRecording) { delete errors.value.title; delete errors.value.prompt; if (!form.classes.length) delete errors.value.classes }
  if (Object.keys(errors.value).length) { await focusError(); return }
  working.value = true; notice.value = ''
  try {
    const data = current.value ? await updateOperation(current.value.id, { ...payload.value, revision: current.value.revision }) : await createOperation(payload.value)
    fill({ ...data, sessions: [] })
    if (continueToRecording) await router.push(destination(data.id, 'record'))
    else { await router.replace(destination(data.id)); noticeType.value = 'success'; notice.value = '草稿已保存。' }
  } catch (error) { noticeType.value = 'error'; notice.value = operationError(error) }
  finally { working.value = false }
}
async function confirmLeave() {
  if (!dirty.value) return true
  try { await ElMessageBox.confirm('题设有未保存的修改，离开后将丢失这些修改。', '离开编辑页面', { type: 'warning', confirmButtonText: '放弃修改并离开', cancelButtonText: '继续编辑' }); return true } catch { return false }
}
function beforeUnload(event) { if (dirty.value) { event.preventDefault(); event.returnValue = '' } }
onBeforeRouteLeave(confirmLeave)
onBeforeRouteUpdate(async to => to.params.questionId === route.params.questionId || await confirmLeave())
watch(() => route.params.questionId, load, { immediate: true })
onMounted(() => window.addEventListener('beforeunload', beforeUnload))
onBeforeUnmount(() => { loadToken++; window.removeEventListener('beforeunload', beforeUnload) })
</script>
