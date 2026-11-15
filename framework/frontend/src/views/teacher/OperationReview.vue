<template>
  <section class="op-page" v-loading="loading">
    <OperationFlow :back-to="backTo" :step="2" title="检查与发布" subtitle="核对学生会看到的题面、初始条件和标准操作，再发布。"><div v-if="current" class="op-version-control"><label for="operation-version">查看版本</label><el-select id="operation-version" :model-value="displayed?.number" class="op-version-select" aria-label="题目版本" @change="selectVersion"><el-option v-for="version in current.versions" :key="version.id" :value="version.number" :label="`v${version.number} · ${operationStatus(version.status)}`" /></el-select></div></OperationFlow>
    <el-alert v-if="notice" :title="notice" :type="noticeType" :closable="false" show-icon role="status" />
    <el-alert v-if="historical" title="正在查看历史版本。历史题面和标准答案只读；新操作从最新版本的初始条件开始。" type="info" :closable="false" show-icon />
    <el-button v-if="loadFailed" @click="load">重新加载题目</el-button>
    <div v-if="displayed && !loadFailed" class="op-review-grid">
      <div class="op-review-main">
        <section class="op-panel"><div class="op-panel-header"><h2>题目内容</h2><router-link v-if="!current.disabled && !historical" :to="destination(current.id)">{{ current.status === 'published' ? '修改并建立新版本' : '修改题设' }}</router-link></div><h3 class="op-question-title">{{ displayed.title || '未命名题目' }}</h3><p class="op-preserve">{{ displayed.prompt || '尚未填写任务说明。' }}</p></section>
        <section class="op-panel"><h2>初始站场条件</h2><dl class="op-facts op-initial-facts"><div><dt>区间许可</dt><dd>{{ displayed.initial.interval_available ? '具备' : '不具备' }}</dd></div><div><dt>预置占用区段</dt><dd>{{ displayed.initial.occupied_sections.join('、') || '全部空闲' }}</dd></div></dl></section>
        <section class="op-panel"><div class="op-panel-header"><div><h2>标准答案</h2><p class="op-help">{{ displayed.standard_log?.length ? `${displayed.standard_log.length} 次业务点击` : '尚未保存标准答案' }}</p></div><el-button v-if="displayed.standard_session_id" :loading="downloading" @click="download(displayed.standard_session_id)">下载日志</el-button></div><OperationLog v-if="displayed.standard_log?.length" :key="displayed.version_id" :events="displayed.standard_log" /><div v-else class="op-empty"><p>进入站场完成标准操作，结束录制并保存答案后，日志会显示在这里。</p><router-link v-if="!current.disabled && !historical && current.status === 'draft'" :to="destination(current.id, 'record')">去录制标准答案 →</router-link></div></section>
      </div>
      <aside>
        <section class="op-panel op-publish-panel"><div class="op-panel-header"><h2>发布状态</h2><span class="op-status" :class="displayed.status">{{ operationStatus(displayed.status) }}</span></div>
          <template v-if="current.disabled"><p>题目已停用。题面、版本和日志仍保留，学生不能新开练习。</p></template>
          <template v-else-if="historical"><p>历史版本 v{{ displayed.number }}。切换至最新版本可继续编辑或发布。</p><el-button style="margin-top:18px" @click="selectVersion(current.number)">返回最新版本</el-button></template>
          <template v-else-if="current.status === 'published'"><p>v{{ current.number }} 已向目标班级公开。需要修改时，可建立新版本。</p><router-link :to="destination(current.id)" class="op-review-primary-link">修改题目</router-link></template>
          <template v-else><p v-if="issues.length">发布前还需要完成：</p><ul v-if="issues.length" class="op-checklist"><li v-for="issue in issues" :key="issue">{{ issue }}</li></ul><p v-else style="margin-bottom:18px">题设和标准答案已齐备，可以发布。</p><el-button type="primary" :disabled="!!issues.length" :loading="working" @click="publish">发布给目标班级</el-button><p v-if="current.published_version">学生当前可见：v{{ current.published_version }}。</p><p>发布后该版本将冻结，修改会建立新版本。</p></template>
        </section>
        <section class="op-panel"><h2>目标班级</h2><div v-if="displayed.classes.length" class="op-tags"><el-tag v-for="name in displayed.classes" :key="name" type="info" effect="plain">{{ name }}</el-tag></div><p v-else class="op-muted">尚未设置</p><p class="op-help">仅班级名称完全匹配的学生可见。</p></section>
        <section class="op-panel op-continue-panel"><h2>继续操作</h2><template v-if="!current.disabled && !historical"><router-link v-if="current.status === 'draft'" :to="destination(current.id, 'record')">{{ current.standard_session_id ? '重新录制答案' : '录制标准答案' }} →</router-link><router-link :to="destination(current.id, 'record', { mode: 'preview' })">预览题目 →</router-link></template><el-button text @click="showRecords = true">查看录制与预览记录</el-button></section>
      </aside>
    </div>
    <el-drawer v-model="showRecords" title="录制与预览记录" size="min(620px, 94vw)" class="op-record-drawer"><div class="op-drawer-content"><el-empty v-if="!current?.sessions?.length" description="尚无录制或预览记录" :image-size="80" /><div v-for="item in sessionPage.items" :key="item.id" class="op-history-item"><div><strong>{{ item.kind === 'preview' ? '预览' : '标准录制' }} · v{{ versionNumber(item.version_id) }}</strong><p>{{ sessionStatus(item.status) }}</p></div><div class="op-actions-group"><router-link :to="destination(current.id, 'record', { session: item.id })">{{ item.owner_id === user.user?.id && item.status === 'active' ? '继续操作' : '查看记录' }}</router-link><el-button link :loading="downloading" @click="download(item.id)">下载</el-button></div></div><ListPager :page="sessionPage.page" :total="sessionPage.total" @change="recordsPage = $event" /></div></el-drawer>
  </section>
</template>
<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/store/user'
import OperationFlow from '@/features/operationQuestions/OperationFlow.vue'
import OperationLog from '@/features/operationQuestions/OperationLog.vue'
import ListPager from '@/components/ListPager.vue'
import { paginate } from '@/domain/pagination'
import { operationLocation, operationReturn, operationStatus, sessionStatus, operationError, publishIssues } from '@/domain/operationPresentation'
import { getOperation, getOperationVersion, publishOperation, downloadOperationLog } from '@/api/operations'
const route = useRoute(), router = useRouter(), user = useUserStore()
const backTo = computed(() => operationReturn(route.query.back))
function destination(id, step = 'edit', query = {}) { return operationLocation(id, step, backTo.value, query) }
const current = ref(null), displayed = ref(null), loading = ref(true), loadFailed = ref(false), working = ref(false), notice = ref(''), noticeType = ref('error'), showRecords = ref(false), recordsPage = ref(1), downloading = ref(false)
const historical = computed(() => !!displayed.value && displayed.value.version_id !== current.value?.version_id)
const issues = computed(() => publishIssues(current.value, current.value?.sessions || []))
const sessionPage = computed(() => paginate(current.value?.sessions || [], recordsPage.value))
let request = 0
function versionNumber(id) { return current.value?.versions?.find(item => item.id === id)?.number || '—' }
async function load() {
  const token = ++request
  loading.value = true; loadFailed.value = false; notice.value = ''
  try {
    const data = await getOperation(route.params.questionId)
    const number = Number(route.query.version)
    const version = number && number !== data.number ? await getOperationVersion(data.id, number) : data
    if (token === request) { current.value = data; displayed.value = version }
  } catch (error) { if (token === request) { noticeType.value = 'error'; notice.value = operationError(error); loadFailed.value = true } }
  finally { if (token === request) loading.value = false }
}
function selectVersion(number) { router.push(destination(current.value.id, 'review', number === current.value.number ? {} : { version: String(number) })) }
async function publish() {
  if (historical.value || issues.value.length || current.value?.disabled || current.value?.status !== 'draft' || working.value) return
  try { await ElMessageBox.confirm(`将 v${current.value.number} 发布给：${current.value.classes.join('、')}。发布后该版本的题设和标准答案将冻结。`, '发布操作题', { confirmButtonText: '确认发布', cancelButtonText: '返回检查', type: 'info' }) } catch { return }
  working.value = true; notice.value = ''
  try { await publishOperation(current.value.id); await load(); noticeType.value = 'success'; notice.value = '题目已发布，目标班级的学生可以查看题面。' } catch (error) { noticeType.value = 'error'; notice.value = operationError(error) } finally { working.value = false }
}
async function download(id) { downloading.value = true; try { await downloadOperationLog(id) } catch (error) { noticeType.value = 'error'; notice.value = operationError(error) } finally { downloading.value = false } }
watch(() => [route.params.questionId, route.query.version], load, { immediate: true })
</script>
<style scoped>
.op-question-title{font-size:22px;line-height:1.6;margin:0 0 18px;overflow-wrap:anywhere}.op-initial-facts{grid-template-columns:1fr 1fr}.op-continue-panel>a{display:block;margin-bottom:15px}.op-continue-panel .el-button{padding:0;white-space:normal;text-align:left}.op-review-primary-link{display:block;text-align:center;padding:10px 16px;background:#0075b7;color:white;border-radius:7px;margin-top:18px}.op-review-primary-link:hover{background:#005e92}@media(max-width:650px){.op-initial-facts{grid-template-columns:1fr}}
</style>
