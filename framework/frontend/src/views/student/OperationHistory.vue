<template>
  <section class="op-page" :aria-busy="loading">
    <header class="op-heading"><div><router-link to="/student/learn/operations">返回</router-link><h1>我的操作记录</h1></div><el-button :loading="loading" @click="load">刷新</el-button></header>
    <el-alert v-if="notice" :title="notice" type="error" :closable="false" role="alert" />
    <div class="op-panel" v-loading="loading"><el-table :data="rows" row-key="session_id"><el-table-column label="题目" min-width="200"><template #default="{row}">{{ row.question.title }} · v{{ row.question.number }}</template></el-table-column><el-table-column label="状态" width="110"><template #default="{row}">{{ attemptStatus(row.status) }}</template></el-table-column><el-table-column label="结果" width="110"><template #default="{row}">{{ outcomeText(row.outcome) }}</template></el-table-column><el-table-column label="开始时间（北京时间）" min-width="180"><template #default="{row}">{{ learningDate(row.created_at) }}</template></el-table-column><el-table-column label="操作" width="120"><template #default="{row}"><router-link :to="{path:'/student/learn/operations/attempts/'+row.session_id,query:{historyPage:String(page)}}">{{ row.status === 'active' ? '继续答题' : '查看记录' }}</router-link></template></el-table-column><template #empty>null</template></el-table><ListPager :page="page" :total="total" @change="changePage" /></div>
  </section>
</template>
<script setup>
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ListPager from '@/components/ListPager.vue'
import { listLearning } from '@/api/operationLearning'
import { attemptStatus, outcomeText, learningError, learningDate } from '@/domain/operationLearning'
import { pageNumber } from '@/domain/pagination'
import '@/features/operationQuestions/operation.css'
const route = useRoute(), router = useRouter()
const rows = ref([]), total = ref(0), page = ref(1), loading = ref(false), notice = ref('')
let request = 0
async function load() {
  const token = ++request; loading.value = true; notice.value = ''; page.value = pageNumber(route.query.page)
  try { const data = await listLearning(page.value); if (token === request) { rows.value = data.items; total.value = data.total; if (page.value > Math.max(1, Math.ceil(data.total / 6))) await changePage(Math.max(1, Math.ceil(data.total / 6))) } }
  catch (e) { if (token === request) { notice.value = learningError(e); rows.value = [] } }
  finally { if (token === request) loading.value = false }
}
function changePage(value) { return router.push({ path: route.path, query: value > 1 ? {page:String(value)} : {} }) }
watch(() => route.query.page, load, { immediate: true })
</script>
