<template>
  <div class="replay" v-loading="store.loading">
    <el-card shadow="never" class="header-card">
      <template #header><strong>操作回放与评分</strong></template>
      <div>{{ store.replayData?.exercise?.title }}</div>
    </el-card>

    <el-card v-if="store.currentAiScore" shadow="never" class="score-card">
      <el-row :gutter="16">
        <el-col :span="6"><el-statistic title="总分" :value="store.currentAiScore.total_score" /></el-col>
        <el-col :span="6"><el-statistic title="正确率" :value="store.currentAiScore.accuracy_score" /></el-col>
        <el-col :span="6"><el-statistic title="效率" :value="store.currentAiScore.efficiency_score" /></el-col>
        <el-col :span="6"><el-statistic title="规范性" :value="store.currentAiScore.operation_quality" /></el-col>
      </el-row>
      <el-alert class="comment" :title="store.currentAiScore.ai_comment" type="success" :closable="false" show-icon />
      <div class="suggestions">
        <el-tag v-for="item in store.currentAiScore.suggestions" :key="item" type="info">{{ item }}</el-tag>
      </div>
    </el-card>
    <el-card v-else shadow="never">
      <el-button type="primary" @click="store.generateAiScore(route.params.sessionId)">生成评分</el-button>
    </el-card>

    <div class="content" v-if="store.replayData">
      <StationCanvas
        :station-detail="stationDetail"
        :snapshot="currentSnapshot"
        selected-entry-signal=""
        selected-exit-signal=""
      />

      <el-card shadow="never" class="timeline-card">
        <template #header><strong>操作时间线</strong></template>
        <el-timeline>
          <el-timeline-item
            v-for="log in store.replayData.logs"
            :key="log.id"
            :type="log.sequence_no === currentSequence ? 'primary' : 'info'"
            :timestamp="`第 ${log.sequence_no} 步`"
          >
            <div class="log-item" @click="currentSequence = log.sequence_no">
              <strong>{{ operationTypeText(log.operation_type) }}</strong>
              <p>{{ log.target_code }} / {{ log.operation_result === 'success' ? '成功' : '失败' }}</p>
              <p v-if="log.error_message" class="error">{{ log.error_message }}</p>
            </div>
          </el-timeline-item>
        </el-timeline>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import StationCanvas from '@/components/StationCanvas/StationCanvas.vue'
import { getStationDetail } from '@/api/interlocking'
import { useExerciseStore } from '@/store/exercise'
import { operationTypeText } from '@/utils/statusText'

const route = useRoute()
const store = useExerciseStore()
const currentSequence = ref(1)
const stationDetail = ref(null)

const currentSnapshot = computed(() => {
  const logs = store.replayData?.logs || []
  const selected = logs.find((log) => log.sequence_no === currentSequence.value) || logs[0]
  return selected?.state_after || store.replayData?.session?.final_snapshot || null
})

onMounted(async () => {
  const replay = await store.loadReplay(route.params.sessionId)
  await store.loadAiScore(route.params.sessionId)
  currentSequence.value = replay.logs[0]?.sequence_no || 1
  stationDetail.value = await getStationDetail(replay.session.station_id)
})
</script>

<style scoped>
.replay {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.content {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 16px;
}

.comment {
  margin-top: 16px;
}

.suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.log-item {
  cursor: pointer;
}

.log-item p {
  margin: 4px 0;
  color: #606266;
}

.error {
  color: #f56c6c;
}

@media (max-width: 1280px) {
  .content {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
