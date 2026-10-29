<template>
  <section class="op-page" :aria-busy="loading">
    <header class="op-heading"><h1>操作学习</h1><el-button :loading="loading" @click="load">刷新</el-button></header>
    <nav class="learning-tabs" aria-label="操作学习管理"><router-link to="/operations/manage">操作题库</router-link><strong aria-current="page">操作批改</strong></nav>
    <form class="review-filters" role="search" @submit.prevent="filter">
      <label>班级<select v-model="className" name="review-class"><option value="">全部班级</option><option v-for="name in classes" :key="name" :value="name">{{ name }}</option></select></label>
      <label>学号<input v-model="studentNumber" name="review-student" type="text" autocomplete="off" spellcheck="false" maxlength="100" placeholder="搜索学号…"></label>
      <label>题目<input v-model="questionSearch" name="review-question" type="text" autocomplete="off" maxlength="200" placeholder="搜索题目标题…"></label>
      <el-button native-type="submit" :loading="loading">筛选</el-button>
    </form>
    <el-alert v-if="notice" :title="notice" type="error" :closable="false" role="alert" />
    <div class="op-panel" v-loading="loading"><el-table :data="rows" row-key="session_id"><el-table-column label="班级 / 学号" min-width="170"><template #default="{row}">{{ row.identity.class_name ?? 'null' }}<br>{{ row.identity.student_id ?? 'null' }}</template></el-table-column><el-table-column label="姓名" min-width="100"><template #default="{row}">{{ row.identity.real_name ?? 'null' }}</template></el-table-column><el-table-column label="题目" min-width="180"><template #default="{row}">{{ row.question.title }} · v{{ row.question.number }}</template></el-table-column><el-table-column label="结果" width="100"><template #default="{row}">{{ outcomeText(row.outcome) }}</template></el-table-column><el-table-column label="评阅状态" width="110"><template #default="{row}">{{ row.review.confirmed ? '已确认查看' : '待查看' }}</template></el-table-column><el-table-column label="操作" width="130"><template #default="{row}"><router-link class="operation-review-link" :to="{path:'/operations/reviews/'+row.session_id,query:{back:route.fullPath}}">查看 / 评阅</router-link></template></el-table-column><template #empty>null</template></el-table><ListPager :page="page" :total="total" @change="changePage" /></div>
  </section>
</template>
<script setup>
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ListPager from '@/components/ListPager.vue'
import { listLearning } from '@/api/operationLearning'
import { getOperationClasses } from '@/api/operations'
import { outcomeText, learningError } from '@/domain/operationLearning'
import { pageNumber } from '@/domain/pagination'
import '@/features/operationQuestions/operation.css'
import '@/features/operationQuestions/learning.css'
const route = useRoute(), router = useRouter()
const rows = ref([]), classes = ref([]), total = ref(0), page = ref(1), loading = ref(false), notice = ref('')
const className = ref(''), studentNumber = ref(''), questionSearch = ref('')
let request = 0
async function load() {
  const token = ++request; loading.value = true; notice.value = ''; page.value = pageNumber(route.query.page)
  className.value = String(route.query.class_name || ''); studentNumber.value = String(route.query.student_number || ''); questionSearch.value = String(route.query.question_search || '')
  try {
    const [data, dictionary] = await Promise.all([listLearning(page.value, filters()), getOperationClasses()])
    if (token !== request) return
    rows.value = data.items; total.value = data.total
    classes.value = [...new Set([...dictionary.items.map(item => item.name), ...data.items.map(item => item.identity.class_name), className.value].filter(Boolean))].sort()
    if (page.value > Math.max(1, Math.ceil(data.total / 6))) await changePage(Math.max(1, Math.ceil(data.total / 6)))
  } catch (e) { if (token === request) { notice.value = learningError(e); rows.value = [] } }
  finally { if (token === request) loading.value = false }
}
function filters() { return { class_name: className.value, student_number: studentNumber.value.trim(), question_search: questionSearch.value.trim() } }
function changePage(value) { return router.push({ path: '/operations/reviews', query: { ...filters(), ...(value > 1 ? {page:String(value)} : {}) } }) }
function filter() { return changePage(1) }
watch(() => route.fullPath, load, { immediate: true })
</script>
