<template>
  <div class="admin-dashboard">
  <section class="authoring-entry"><div><span>出题与批阅</span><h2>从命题到反馈，在后台完成</h2><p>自行编辑题干、答案和评分细则，预览发布后集中处理学生作答。</p></div><div><router-link to="/admin/questions">管理题库</router-link><router-link to="/admin/questions/new">＋ 自行出题</router-link><router-link to="/admin/grading">进入批阅中心 →</router-link></div></section>
  <PracticePath />
  <div class="section-title-row"><div><span class="section-overline">PLATFORM OVERVIEW</span><h2>平台运行概览</h2></div><router-link to="/teacher/exercises">管理仿真练习 ↗</router-link></div>
  <el-card shadow="never" v-loading="loading" class="admin-overview-card">
    <template #header><strong>系统管理</strong><span class="admin-card-caption">用户与教学数据</span></template>
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
          <el-button size="small" type="danger" plain @click="removeUser(row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessageBox } from 'element-plus'

import { deleteAdminUser, getAdminOverview, listAdminUsers } from '@/api/admin'
import PracticePath from '@/components/PracticePath.vue'

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

async function removeUser(userId) {
  await ElMessageBox.confirm('确认删除该用户？', '提示')
  await deleteAdminUser(userId)
  await loadData()
}

onMounted(loadData)
</script>

<style scoped>
.authoring-entry{display:flex;justify-content:space-between;align-items:center;gap:24px;padding:25px 28px;margin-bottom:25px;background:#eaf4fb;border:1px solid #b9d6e8;border-radius:9px}.authoring-entry span{font-size:var(--ui-text-meta);letter-spacing:2px;color:#5e8aa6}.authoring-entry h2{font-size:24px;margin:12px 0}.authoring-entry p{font-size:var(--ui-text-base);color:#586f82;line-height:1.8}.authoring-entry>div:last-child{display:flex;gap:10px;flex-wrap:wrap}.authoring-entry a{padding:11px 14px;border:1px solid #b9d6e8;background:white;border-radius:6px;font-size:var(--ui-text-base);white-space:nowrap}.authoring-entry a:last-child{background:#0075b7;color:white;border-color:#0075b7}@media(max-width:1000px){.authoring-entry{flex-direction:column;align-items:flex-start}}
.admin-card-caption { color: #586f82; margin-left: 15px; font-size: var(--ui-text-meta); font-weight: 400; }
.overview {
  margin-bottom: 20px;
}
</style>
