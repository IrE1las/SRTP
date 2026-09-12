<template>
  <div class="workbench" v-loading="exerciseStore.loading || runtimeStore.loading">
    <el-card shadow="never" class="header-card">
      <div class="header">
        <div>
          <h2>{{ exerciseStore.currentExercise?.title || '练习中' }}</h2>
          <p>{{ exerciseStore.currentExercise?.description }}</p>
        </div>
        <el-statistic title="剩余时间" :value="exerciseStore.remainingSeconds" suffix="秒" />
      </div>
    </el-card>

    <div class="content">
      <StationCanvas
        :station-detail="exerciseStore.stationDetail"
        :snapshot="exerciseStore.snapshot"
        :selected-entry-signal="runtimeStore.selectedEntrySignal"
        :selected-exit-signal="runtimeStore.selectedExitSignal"
        @signal-click="runtimeStore.selectSignal"
        @switch-click="runtimeStore.operateSwitch"
        @section-click="runtimeStore.toggleSectionOccupancy"
      />

      <el-card shadow="never" class="side-panel">
        <template #header>
          <strong>练习状态</strong>
        </template>
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="会话状态">{{ sessionStatusText(exerciseStore.currentSession?.status) }}</el-descriptions-item>
          <el-descriptions-item label="完成状态">{{ completionStatusText(exerciseStore.currentSession?.completion_status) }}</el-descriptions-item>
          <el-descriptions-item label="始端">{{ runtimeStore.selectedEntrySignal || '未选择' }}</el-descriptions-item>
          <el-descriptions-item label="终端">{{ runtimeStore.selectedExitSignal || '未选择' }}</el-descriptions-item>
          <el-descriptions-item label="最近操作">{{ runtimeStore.lastActionMessage || '-' }}</el-descriptions-item>
        </el-descriptions>

        <el-divider content-position="left">活动进路</el-divider>
        <el-empty v-if="activeRoutes.length === 0" description="暂无进路" :image-size="70" />
        <el-card v-for="route in activeRoutes" :key="route.route_name" class="route-card" shadow="never">
          <div>{{ route.route_name }}</div>
          <el-button size="small" type="danger" plain @click="runtimeStore.cancelRoute(route.entry_signal)">取消</el-button>
        </el-card>

        <el-button type="warning" plain class="finish-button" @click="finishExercise">结束练习</el-button>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import StationCanvas from '@/components/StationCanvas/StationCanvas.vue'
import { useExerciseStore } from '@/store/exercise'
import { useExerciseInterlockingStore } from '@/store/exerciseInterlocking'
import { completionStatusText, sessionStatusText } from '@/utils/statusText'

const route = useRoute()
const router = useRouter()
const exerciseStore = useExerciseStore()
const runtimeStore = useExerciseInterlockingStore()

const activeRoutes = computed(() => exerciseStore.snapshot?.active_routes || [])

onMounted(async () => {
  await exerciseStore.startExercise(route.params.id)
})

watch(
  () => exerciseStore.currentSession?.status,
  (status) => {
    if (status && status !== 'ongoing') {
      router.push('/student/history')
    }
  },
)

async function finishExercise() {
  await exerciseStore.finishExercise('aborted')
  router.push('/student/history')
}
</script>
