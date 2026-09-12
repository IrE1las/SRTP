<template>
  <el-card shadow="never">
    <template #header>
      <strong>练习历史</strong>
    </template>

    <el-table :data="store.historyList" v-loading="store.loading" border>
      <el-table-column prop="id" label="会话" width="90" />
      <el-table-column label="状态" width="110">
        <template #default="{ row }">{{ sessionStatusText(row.status) }}</template>
      </el-table-column>
      <el-table-column label="完成结果" width="120">
        <template #default="{ row }">{{ completionStatusText(row.completion_status) }}</template>
      </el-table-column>
      <el-table-column prop="total_time" label="耗时(秒)" width="110" />
      <el-table-column prop="total_clicks" label="点击数" width="100" />
      <el-table-column label="操作" width="140">
        <template #default="{ row }">
          <el-button size="small" type="primary" plain @click="router.push(`/student/history/${row.id}`)">
            回放/评分
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'

import { useExerciseStore } from '@/store/exercise'
import { completionStatusText, sessionStatusText } from '@/utils/statusText'

const router = useRouter()
const store = useExerciseStore()

onMounted(() => store.loadHistory())
</script>
