<template>
  <section class="op-page exam-page" v-loading="loading">
    <header class="exam-masthead"><div><p class="exam-kicker">标准站 · 操作考试</p><h1>考试管理</h1><p>设置考试安排，发布给班级，查看学生操作记录。</p></div><div class="exam-tools"><el-button @click="load">刷新列表</el-button><router-link class="el-button el-button--primary" to="/exams/manage/new">新建考试</router-link></div></header>
    <el-alert v-if="notice" :title="notice" type="error" :closable="false" role="alert" />
    <section class="exam-list-panel"><div class="exam-list-toolbar"><strong>{{ user.role === 'admin' ? '全部考试' : '我发布的考试' }}</strong><p>共 {{ total }} 场 · 时间为北京时间</p></div>
      <el-table :data="items" empty-text="暂无考试，点击“新建考试”开始设置。">
        <el-table-column label="考试 / 班级" min-width="240"><template #default="{row}"><router-link class="exam-row-title" :to="`/exams/manage/${row.id}`">{{ row.name || '未命名草稿' }}</router-link><p class="exam-time">{{ row.classes.join('、') || 'null' }}</p></template></el-table-column>
        <el-table-column label="开放 / 截止" min-width="210"><template #default="{row}"><div class="exam-time">{{ beijingTime(row.opens_at) }}<br>{{ beijingTime(row.closes_at) }}</div></template></el-table-column>
        <el-table-column label="状态" width="110"><template #default="{row}"><span class="exam-badge" :class="row.status">{{ examStates[row.status] }}</span></template></el-table-column>
        <el-table-column label="名单人数" width="110" align="right"><template #default="{row}"><span class="exam-count">{{ row.participant_count }}</span></template></el-table-column>
        <el-table-column label="答卷份数" width="110" align="right"><template #default="{row}"><span class="exam-count">{{ row.attempt_count }}</span></template></el-table-column>
        <el-table-column label="操作" width="140"><template #default="{row}"><router-link class="exam-table-link" :to="`/exams/manage/${row.id}`">{{ row.status === 'draft' ? '编辑草稿 →' : '查看考试 →' }}</router-link></template></el-table-column>
      </el-table><ListPager :page="page" :total="total" @change="changePage" />
    </section>
  </section>
</template>
<script setup>
import '@/features/exams/exam.css'
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/store/user'
import ListPager from '@/components/ListPager.vue'
import { listExams } from '@/api/exams'
import { beijingTime, examStates, examError } from '@/domain/exams'
const route = useRoute(), router = useRouter(), user = useUserStore(), loading = ref(false), notice = ref(''), items = ref([]), total = ref(0), page = ref(Math.max(1, Number(route.query.page) || 1))
async function load() { loading.value = true; notice.value = ''; try { const data = await listExams(page.value); items.value = data.items; total.value = data.total } catch (error) { notice.value = examError(error) } finally { loading.value = false } }
async function changePage(value) { page.value = value; await router.replace({query:{page:value}}); await load() }
onMounted(load)
</script>
