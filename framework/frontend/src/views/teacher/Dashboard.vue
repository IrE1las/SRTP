<template>
  <div class="teacher-dashboard">
  <div class="section-title-row"><div><span class="section-overline">TEACHING OVERVIEW</span><h2>教学数据概览</h2></div><router-link to="/teacher/exercises">管理练习 ↗</router-link></div>
  <el-card shadow="never" v-loading="loading" class="statistics-card">
    <template #header><strong>教学统计</strong></template>
    <el-row :gutter="16">
      <el-col :span="6"><el-statistic title="题目数量" :value="stats.exercise_count || 0" /></el-col>
      <el-col :span="6"><el-statistic title="练习次数" :value="stats.session_count || 0" /></el-col>
      <el-col :span="6"><el-statistic title="完成率" :value="stats.completion_rate || 0" suffix="%" /></el-col>
      <el-col :span="6"><el-statistic title="平均分" :value="stats.average_score || 0" /></el-col>
    </el-row>
  </el-card>
  <div class="teacher-actions"><router-link to="/teacher/exercises/new"><strong>创建新的练习</strong><span>设计进路任务，引导学生学以致用 →</span></router-link><router-link to="/teacher/exercises"><strong>管理我的题库</strong><span>整理教学内容，查看已发布的练习 →</span></router-link></div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'

import { getTeacherStatistics } from '@/api/statistics'

const stats = ref({})
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    stats.value = await getTeacherStatistics()
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
