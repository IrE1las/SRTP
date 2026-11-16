<template>
  <div class="teacher-dashboard">
  <div class="section-title-row"><div><h2>教学数据概览</h2></div><router-link to="/teacher/chapter-bank">管理客观题库 ↗</router-link></div>
  <el-alert v-if="notice" :title="notice" type="error" :closable="false" />
  <el-card shadow="never" v-loading="loading" class="statistics-card">
    <template #header><strong>教学统计</strong></template>
    <el-row :gutter="16">
      <el-col :span="6"><el-statistic title="客观题数量" :value="stats.question_count || 0" /></el-col>
      <el-col :span="6"><el-statistic title="已交卷答卷" :value="stats.submitted_count || 0" /></el-col>
      <el-col :span="6"><el-statistic title="待发布成绩" :value="stats.pending_count || 0" /></el-col>
      <el-col :span="6"><el-statistic title="已发布成绩" :value="stats.published_count || 0" /></el-col>
    </el-row>
  </el-card>
  <div class="teacher-actions"><router-link to="/teacher/chapter-bank"><strong>管理客观题库</strong></router-link><router-link to="/exams/grading"><strong>进入考试批阅</strong></router-link></div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'

import { listChapterQuestions } from '@/api/chapterAuthoring'
import { examReviews } from '@/api/exams'

const stats = ref({})
const notice = ref('')
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    const [bank, reviews] = await Promise.all([listChapterQuestions({limit:1}), examReviews({status:'all'})])
    stats.value = {question_count:bank.total, submitted_count:reviews.counts.all, pending_count:reviews.counts.pending, published_count:reviews.counts.published}
  } catch (error) {
    notice.value = typeof error.response?.data?.detail === 'string' ? error.response.data.detail : '教学数据加载失败，请刷新重试'
  } finally {
    loading.value = false
  }
})
</script>
<style scoped>
.teacher-actions { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px; }
.teacher-actions a { background: white; border: 1px solid #e6ebf1; border-radius: 9px; padding: 28px; display: flex; flex-direction: column; gap: 14px; }
.teacher-actions strong { font-size: var(--ui-text-lead); font-weight: 500; color: #19334d; }
.teacher-actions span { color: #586f82; font-size: var(--ui-text-base); line-height: 1.8; }
.teacher-actions a:hover { border-color: #9fc6e0; }
@media (max-width: 600px) { .teacher-actions { grid-template-columns: 1fr; } }
</style>
