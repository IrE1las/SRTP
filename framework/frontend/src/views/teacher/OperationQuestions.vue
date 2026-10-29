<template>
  <section class="op-page" :aria-busy="loading">

    <header class="op-heading"><div><h1>操作学习</h1><p class="op-muted">操作题库 · 设置题目，录制标准答案，再发布给指定班级。</p></div><router-link :to="newLocation" class="op-primary-link">＋ 新建操作题</router-link></header>
    <nav class="learning-tabs" aria-label="操作学习管理"><strong aria-current="page">操作题库</strong><router-link to="/operations/reviews">操作批改</router-link></nav>
    <div class="op-panel">
      <div class="op-toolbar">
        <form class="op-search" role="search" @submit.prevent="applyFilters"><el-input v-model="search" name="operation-search" aria-label="按题目标题或班级搜索" maxlength="200" placeholder="搜索标题或班级…" clearable autocomplete="off" @clear="applyFilters" /><el-button native-type="submit" :loading="loading">搜索</el-button></form>
        <div class="op-filters"><label for="operation-status">状态</label><el-select id="operation-status" v-model="filter" aria-label="题目状态" @change="applyFilters"><el-option label="全部状态" value="all" /><el-option label="草稿" value="draft" /><el-option label="已发布" value="published" /><el-option label="已停用" value="disabled" /></el-select><el-button @click="load" :loading="loading">刷新</el-button></div>
      </div>
      <el-alert v-if="notice" :title="notice" type="error" show-icon :closable="false" role="alert" />
      <div v-loading="loading" class="op-table-area">
        <el-table v-if="rows.length" :data="rows" row-key="id">
          <el-table-column label="题目" min-width="240"><template #default="{ row }"><router-link :to="destination(row.id, row.status === 'draft' ? 'edit' : 'review')" class="op-title-link">{{ row.title || '未命名题目' }}</router-link><div class="op-help">v{{ row.number }}<span v-if="row.published_version && row.published_version !== row.number"> · 已发布 v{{ row.published_version }}</span></div></template></el-table-column>
          <el-table-column label="状态" width="110"><template #default="{ row }"><span class="op-status" :class="row.status">{{ operationStatus(row.status) }}</span></template></el-table-column>
          <el-table-column label="目标班级" min-width="180"><template #default="{ row }"><div v-if="row.classes.length" class="op-tags"><el-tag v-for="name in row.classes" :key="name" type="info" effect="plain">{{ name }}</el-tag></div><span v-else class="op-muted">尚未设置</span></template></el-table-column>
          <el-table-column label="操作" min-width="220"><template #default="{ row }"><div class="op-row-actions"><router-link :to="destination(row.id, 'review')">查看题目</router-link><router-link v-if="!row.disabled" :to="destination(row.id)">{{ row.status === 'published' ? '修改题目' : '编辑草稿' }}</router-link><el-button v-if="!row.disabled" link type="danger" :disabled="working" @click="disable(row)">停用</el-button><el-button link type="danger" :disabled="working" @click="remove(row)">删除</el-button></div></template></el-table-column>
        </el-table>
        <div v-else-if="!loading && !notice" class="op-empty"><h2>{{ filtered ? '没有找到匹配的题目' : '还没有操作题' }}</h2><p>{{ filtered ? '试试其他关键词，或清除筛选查看全部题目。' : '从一道练习开始：填写任务，操作站场录制答案，然后发布。' }}</p><el-button v-if="filtered" @click="clearFilters">清除筛选</el-button><router-link v-else :to="newLocation" class="op-primary-link">新建第一道题</router-link></div>
      </div>
      <ListPager :page="page" :total="total" @change="changePage" />
    </div>
  </section>
</template>
<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/store/user'
import ListPager from '@/components/ListPager.vue'
import { pageNumber } from '@/domain/pagination'
import { operationBase, operationLocation, operationReturn, operationStatus, operationError } from '@/domain/operationPresentation'
import { listOperations, disableOperation, deleteOperation } from '@/api/operations'
import '@/features/operationQuestions/operation.css'
import '@/features/operationQuestions/learning.css'
const user = useUserStore(), route = useRoute(), router = useRouter()
const rows = ref([]), page = ref(1), total = ref(0), loading = ref(false), working = ref(false), notice = ref(''), search = ref(''), filter = ref('all')
const filtered = computed(() => !!route.query.search || (route.query.status && route.query.status !== 'all'))
const newLocation = computed(() => ({ path: operationBase + '/new', query: route.fullPath === operationBase ? {} : { back: route.fullPath } }))
function destination(id, step = 'edit', query = {}) { return operationLocation(id, step, route.query.question ? '/operations/manage' : route.fullPath, query) }
let request = 0
async function load() {
  if (/^\d+$/.test(String(route.query.question))) {
    await router.replace(destination(route.query.question, route.query.session ? 'record' : 'edit', route.query.session ? { session: String(route.query.session) } : {}))
    return
  }
  const token = ++request
  page.value = pageNumber(route.query.page)
  search.value = String(route.query.search || '')
  filter.value = ['draft', 'published', 'disabled'].includes(route.query.status) ? route.query.status : 'all'
  loading.value = true; notice.value = ''
  try {
    const data = await listOperations(page.value, { search: search.value, status: filter.value })
    if (token !== request) return
    rows.value = data.items; total.value = data.total
    const last = Math.max(1, Math.ceil(data.total / 6))
    if (page.value > last) await changePage(last)
  } catch (error) { if (token === request) { rows.value = []; total.value = 0; notice.value = operationError(error, '题库加载失败，请刷新重试。') } }
  finally { if (token === request) loading.value = false }
}
function query(value = 1) { return { ...(search.value.trim() ? { search: search.value.trim() } : {}), ...(filter.value !== 'all' ? { status: filter.value } : {}), ...(value > 1 ? { page: String(value) } : {}) } }
function applyFilters() { router.push({ path: operationBase, query: query() }) }
function clearFilters() { search.value = ''; filter.value = 'all'; router.push(operationBase) }
function changePage(value) { return router.push({ path: operationBase, query: query(value) }) }
async function disable(row) {
  try { await ElMessageBox.confirm(`停用“${row.title || '未命名题目'}”后，学生将无法新开练习。已有版本和日志会保留。`, '停用题目', { type: 'warning', confirmButtonText: '停用题目', cancelButtonText: '取消' }) } catch { return }
  working.value = true; notice.value = ''
  try { await disableOperation(row.id); await load() } catch (error) { notice.value = operationError(error) } finally { working.value = false }
}
async function remove(row) {
  try { await ElMessageBox.confirm(`永久删除“${row.title || '未命名题目'}”及其全部版本、标准答案和录制/预览日志？此操作无法恢复。`, '删除操作题', { type:'warning', confirmButtonText:'永久删除', cancelButtonText:'取消' }) } catch { return }
  working.value = true; notice.value = ''
  try { await deleteOperation(row.id); await load() } catch (error) { notice.value = operationError(error) } finally { working.value = false }
}
watch(() => route.fullPath, load, { immediate: true })
</script>
<style scoped>
.op-primary-link{display:inline-flex;align-items:center;justify-content:center;min-height:44px;padding:10px 20px;border-radius:7px;background:#0075b7;color:white;font-weight:600;font-size:16px;white-space:nowrap}.op-primary-link:hover{background:#005e92}.op-table-area{min-height:200px}
</style>
