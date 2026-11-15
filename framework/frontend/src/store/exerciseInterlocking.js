import { defineStore } from 'pinia'
import { ElMessage } from 'element-plus'

import {
  arrangeRouteInSession,
  cancelRouteInSession,
  manualUnlockInSession,
  operateSwitchInSession,
  updateSectionOccupancyInSession,
} from '@/api/exerciseRuntime'
import { useExerciseStore } from '@/store/exercise'

export const useExerciseInterlockingStore = defineStore('exerciseInterlocking', {
  state: () => ({
    selectedEntrySignal: '',
    selectedExitSignal: '',
    loading: false,
    lastActionMessage: '',
  }),
  actions: {
    clearSelection() {
      this.selectedEntrySignal = ''
      this.selectedExitSignal = ''
    },
    async selectSignal(signalCode) {
      if (!this.selectedEntrySignal) {
        this.selectedEntrySignal = signalCode
        this.selectedExitSignal = ''
        this.lastActionMessage = `已选择始端信号机 ${signalCode}`
        return
      }
      if (this.selectedEntrySignal === signalCode) {
        this.clearSelection()
        this.lastActionMessage = '已取消信号机选择'
        return
      }
      this.selectedExitSignal = signalCode
      await this.arrangeSelectedRoute()
    },
    async arrangeSelectedRoute() {
      const exerciseStore = useExerciseStore()
      if (!exerciseStore.currentSession) return
      this.loading = true
      try {
        const result = await arrangeRouteInSession({
          session_id: exerciseStore.currentSession.id,
          entry_signal: this.selectedEntrySignal,
          exit_signal: this.selectedExitSignal,
        })
        exerciseStore.updateRuntime(result)
        this.lastActionMessage = result.message
        this.clearSelection()
        ElMessage.success(result.message)
      } finally {
        this.loading = false
      }
    },
    async operateSwitch(switchCode, targetPosition) {
      const exerciseStore = useExerciseStore()
      if (!exerciseStore.currentSession) return
      this.loading = true
      try {
        const result = await operateSwitchInSession({
          session_id: exerciseStore.currentSession.id,
          switch_code: switchCode,
          target_position: targetPosition,
        })
        exerciseStore.updateRuntime(result)
        this.lastActionMessage = result.message
        ElMessage.success(result.message)
      } finally {
        this.loading = false
      }
    },
    async toggleSectionOccupancy(sectionCode) {
      const exerciseStore = useExerciseStore()
      if (!exerciseStore.currentSession) return
      const occupied = exerciseStore.snapshot?.sections?.[sectionCode]?.occupancy === 'occupied'
      this.loading = true
      try {
        const result = await updateSectionOccupancyInSession({
          session_id: exerciseStore.currentSession.id,
          section_code: sectionCode,
          occupied: !occupied,
        })
        exerciseStore.updateRuntime(result)
        this.lastActionMessage = result.message
        ElMessage.success(result.message)
      } finally {
        this.loading = false
      }
    },
    async cancelRoute(signalCode) {
      const exerciseStore = useExerciseStore()
      if (!exerciseStore.currentSession) return
      const result = await cancelRouteInSession({ session_id: exerciseStore.currentSession.id, signal_code: signalCode })
      exerciseStore.updateRuntime(result)
      this.lastActionMessage = result.message
      ElMessage.success(result.message)
    },
    async manualUnlock(sectionCode) {
      const exerciseStore = useExerciseStore()
      if (!exerciseStore.currentSession) return
      const result = await manualUnlockInSession({ session_id: exerciseStore.currentSession.id, section_code: sectionCode })
      exerciseStore.updateRuntime(result)
      this.lastActionMessage = result.message
      ElMessage.success(result.message)
    },
  },
})
