<template>
  <div class="dashboard-page">
  <div class="section-title-row"><div><span class="section-overline">MY LEARNING</span><h2>我的学习足迹</h2></div><router-link to="/student/history">查看练习历史 ↗</router-link></div>
  <el-card shadow="never" v-loading="loading" class="statistics-card">
    <template #header><strong>学习概览</strong></template>
    <el-row :gutter="16">
      <el-col :span="6"><el-statistic title="练习次数" :value="stats.total_sessions || 0" /></el-col>
      <el-col :span="6"><el-statistic title="完成次数" :value="stats.completed_sessions || 0" /></el-col>
      <el-col :span="6"><el-statistic title="平均分" :value="stats.average_score || 0" /></el-col>
      <el-col :span="6"><el-statistic title="错误操作" :value="stats.wrong_operation_count || 0" /></el-col>
    </el-row>
  </el-card>
  <PracticePath />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'

import { getMyStatistics } from '@/api/statistics'
import PracticePath from '@/components/PracticePath.vue'

const stats = ref({})
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    stats.value = await getMyStatistics()
  } finally {
    loading.value = false
  }
})
</script>
