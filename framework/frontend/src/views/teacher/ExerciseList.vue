<template>
  <el-card shadow="never">
    <template #header>
      <div class="page-header">
        <strong>题库管理</strong>
        <el-button type="primary" @click="router.push('/teacher/exercises/new')">新建练习</el-button>
      </div>
    </template>

    <el-table :data="store.teacherExercises" v-loading="store.loading" border>
      <el-table-column prop="title" label="题目" min-width="180" />
      <el-table-column prop="difficulty" label="难度" width="100" />
      <el-table-column prop="time_limit" label="限时(秒)" width="110" />
      <el-table-column label="目标进路" min-width="180">
        <template #default="{ row }">
          {{ formatTargets(row.target_routes) }}
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '已发布' : '停用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="router.push(`/teacher/exercises/${row.id}/edit`)">编辑</el-button>
          <el-button size="small" type="danger" plain @click="store.deleteExercise(row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'

import { useExerciseStore } from '@/store/exercise'

const router = useRouter()
const store = useExerciseStore()

onMounted(() => store.loadTeacherExercises())

function formatTargets(targets) {
  return (targets || []).map((item) => `${item.entry_signal}→${item.exit_signal}`).join('、')
}
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
</style>
