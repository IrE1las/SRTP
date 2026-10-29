<template>
  <section class="op-page exam-page" v-loading="loading"><router-link class="op-back" to="/student/exams">← 返回考试界面</router-link>
    <header class="exam-masthead"><div><p class="exam-kicker">标准站 · 本人记录</p><h1>历史考试</h1><p>查看已交卷的考试与保存的操作记录。</p></div><el-button @click="load">刷新记录</el-button></header>
    <el-alert v-if="notice" :title="notice" type="error" :closable="false" />
    <section class="exam-list-panel"><el-table :data="items" empty-text="暂无已完成考试"><el-table-column prop="name" label="考试名称" min-width="180" /><el-table-column label="开始时间（北京时间）" min-width="190"><template #default="{row}">{{ beijingTime(row.started_at) }}</template></el-table-column><el-table-column prop="finish_reason_text" label="交卷原因" min-width="160" /><el-table-column label="状态" min-width="240"><template #default>{{ completedMessage }}</template></el-table-column><el-table-column label="操作" width="130"><template #default="{row}"><router-link class="exam-table-link" :to="{path:`/student/exams/attempts/${row.session_id}`,query:{back:page}}">查看本人记录</router-link></template></el-table-column></el-table>
    <ListPager :page="page" :total="total" @change="changePage" /></section>
  </section>
</template>
<script setup>
import '@/features/exams/exam.css'
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ListPager from '@/components/ListPager.vue'
import { examHistory } from '@/api/exams'
import { beijingTime, completedMessage, examError } from '@/domain/exams'
const route = useRoute(), router = useRouter(), page = ref(Math.max(1, Number(route.query.page) || 1)), items = ref([]), total = ref(0), loading = ref(false), notice = ref('')
async function load() { loading.value = true; notice.value = ''; try { const data = await examHistory(page.value); items.value = data.items; total.value = data.total } catch (error) { notice.value = examError(error) } finally { loading.value = false } }
async function changePage(value) { page.value = value; await router.replace({ query: { page: value } }); await load() }
onMounted(load)
</script>
