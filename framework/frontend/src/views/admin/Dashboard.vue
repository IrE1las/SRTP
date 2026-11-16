<template>
  <div class="admin-dashboard">
  <div class="section-title-row"><div><h2>平台运行概览</h2></div><router-link to="/admin/users">用户管理 ↗</router-link></div>
  <el-card shadow="never" v-loading="loading" class="admin-overview-card">
    <template #header><strong>系统管理</strong></template>
    <el-row :gutter="16" class="overview">
      <el-col :span="6"><el-statistic title="用户数" :value="overview.user_count || 0" /></el-col>
      <el-col :span="6"><el-statistic title="练习题" :value="overview.exercise_count || 0" /></el-col>
      <el-col :span="6"><el-statistic title="练习会话" :value="overview.session_count || 0" /></el-col>
      <el-col :span="6"><el-statistic title="操作日志" :value="overview.operation_log_count || 0" /></el-col>
    </el-row>
    <el-table :data="users" border>
      <el-table-column prop="username" label="用户名" />
      <el-table-column prop="real_name" label="姓名" />
      <el-table-column prop="role" label="角色" />
      <el-table-column prop="class_name" label="班级" />
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <router-link to="/admin/users">管理账号</router-link>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'

import { getAdminOverview, listAdminUsers } from '@/api/admin'

const overview = ref({})
const users = ref([])
const loading = ref(false)

async function loadData() {
  loading.value = true
  try {
    overview.value = await getAdminOverview()
    users.value = await listAdminUsers()
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>

.overview {
  margin-bottom: 20px;
}
</style>
