<template>
  <section class="op-page" :aria-busy="loading">
    <header class="op-heading"><h1>操作学习</h1><div class="op-actions-group"><router-link to="/student/learn/operations/history">我的操作记录</router-link><el-button :loading="loading" @click="load">刷新</el-button></div></header>
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" role="alert" />
    <div v-loading="loading" class="op-catalogue-list">
      <article v-for="question in rows" :key="question.id" class="op-panel"><div class="op-panel-header"><span class="op-muted">标准站 · v{{ question.number }}</span></div><h2>{{ question.title }}</h2><p class="op-preserve">{{ question.prompt }}</p><dl class="op-facts op-catalogue-conditions"><div><dt>区间许可</dt><dd>{{ question.initial.interval_available ? '具备' : '不具备' }}</dd></div><div><dt>预置占用区段</dt><dd>{{ question.initial.occupied_sections.join('、') || '全部空闲' }}</dd></div></dl><el-button type="primary" :loading="starting === question.id" :disabled="!!starting" @click="start(question)">开始 / 继续答题</el-button></article>
      <div v-if="!loading && !error && !rows.length" class="op-panel op-empty"><h2>本班暂无操作题</h2><p>null</p></div>
    </div>
    <ListPager :page="page" :total="total" @change="changePage" />
  </section>
</template>
<script setup>
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ListPager from '@/components/ListPager.vue'
import { pageNumber } from '@/domain/pagination'
import { listOperations } from '@/api/operations'
import { beginLearning } from '@/api/operationLearning'
import { learningError } from '@/domain/operationLearning'
import '@/features/operationQuestions/operation.css'
const route = useRoute(), router = useRouter()
const rows = ref([]), total = ref(0), page = ref(1), loading = ref(false), error = ref('')
const starting = ref(null)
async function start(question) {
  if (starting.value) return
  starting.value = question.id; error.value = ''
  try {
    const attempt = await beginLearning(question.id)
    await router.push({ path: '/student/learn/operations/attempts/' + attempt.session_id, query: page.value > 1 ? { backPage: String(page.value) } : {} })
  } catch (e) { error.value = learningError(e) }
  finally { starting.value = null }
}
let request = 0
async function load() {
  const token = ++request
  page.value = pageNumber(route.query.page); loading.value = true; error.value = ''
  try {
    const data = await listOperations(page.value)
    if (token === request) {
      rows.value = data.items; total.value = data.total
      const last = Math.max(1, Math.ceil(data.total / 6))
      if (page.value > last) await changePage(last)
    }
  } catch { if (token === request) { error.value = '操作题加载失败，请点击刷新重试。'; rows.value = []; total.value = 0 } }
  finally { if (token === request) loading.value = false }
}
function changePage(value) { return router.push({ path: route.path, query: value > 1 ? { page: String(value) } : {} }) }
watch(() => route.query.page, load, { immediate: true })
</script>
<style scoped>
.op-catalogue-list{min-height:180px}.op-catalogue-list h2{font-size:22px;overflow-wrap:anywhere}.op-catalogue-conditions{grid-template-columns:1fr 1fr;background:#f5f8fb;padding:20px;margin:24px 0}.op-catalogue-list .op-panel-header{font-size:14px}@media(max-width:650px){.op-catalogue-conditions{grid-template-columns:1fr}}
</style>
