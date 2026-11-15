import { defineStore } from 'pinia'
import { ElMessage } from 'element-plus'

import { generateAiScore as generateAiScoreApi, getAiScore } from '@/api/aiScore'

import {
  createExercise,
  deleteExercise as deleteExerciseApi,
  finishExercise as finishExerciseApi,
  getExercise,
  getExerciseHistory,
  getExerciseReplay,
  listLobbyExercises,
  listTeacherExercises,
  startExercise as startExerciseApi,
  updateExercise,
} from '@/api/exercise'

export const useExerciseStore = defineStore('exercise', {
  state: () => ({
    lobbyExercises: [],
    teacherExercises: [],
    currentExercise: null,
    currentSession: null,
    stationDetail: null,
    snapshot: null,
    deadlineAt: null,
    timerNow: Date.now(),
    timerId: null,
    historyList: [],
    replayData: null,
    currentAiScore: null,
    loading: false,
  }),
  getters: {
    remainingSeconds: (state) => {
      if (!state.deadlineAt) return 0
      const value = state.deadlineAt
      const deadline = new Date(/(?:Z|[+-]\d{2}:\d{2})$/i.test(value) ? value : `${value}Z`).getTime()
      if (Number.isNaN(deadline)) return 0
      return Math.max(0, Math.floor((deadline - state.timerNow) / 1000))
    },
  },
  actions: {
    async loadLobby() {
      this.loading = true
      try {
        this.lobbyExercises = await listLobbyExercises()
      } finally {
        this.loading = false
      }
    },
    async loadTeacherExercises() {
      this.loading = true
      try {
        this.teacherExercises = await listTeacherExercises()
      } finally {
        this.loading = false
      }
    },
    async loadExercise(exerciseId) {
      return getExercise(exerciseId)
    },
    async saveExercise(payload, exerciseId = null) {
      const result = exerciseId ? await updateExercise(exerciseId, payload) : await createExercise(payload)
      ElMessage.success('练习题已保存')
      return result
    },
    async deleteExercise(exerciseId) {
      await deleteExerciseApi(exerciseId)
      ElMessage.success('练习题已删除')
      await this.loadTeacherExercises()
    },
    async startExercise(exerciseId) {
      this.loading = true
      try {
        const payload = await startExerciseApi(exerciseId)
        this.currentExercise = payload.exercise
        this.currentSession = payload.session
        this.stationDetail = payload.station_detail
        this.snapshot = payload.snapshot
        this.deadlineAt = payload.deadline_at
        this.startTimer()
        return payload
      } finally {
        this.loading = false
      }
    },
    async finishExercise(reason = 'aborted') {
      if (!this.currentSession) return null
      const session = await finishExerciseApi(this.currentSession.id, reason)
      this.currentSession = session
      this.stopTimer()
      return session
    },
    async loadHistory() {
      this.loading = true
      try {
        this.historyList = await getExerciseHistory()
      } finally {
        this.loading = false
      }
    },
    async loadReplay(sessionId) {
      this.loading = true
      try {
        this.replayData = await getExerciseReplay(sessionId)
        return this.replayData
      } finally {
        this.loading = false
      }
    },
    async loadAiScore(sessionId) {
      try {
        this.currentAiScore = await getAiScore(sessionId)
      } catch {
        this.currentAiScore = null
      }
      return this.currentAiScore
    },
    async generateAiScore(sessionId) {
      this.currentAiScore = await generateAiScoreApi(sessionId)
      ElMessage.success('评分已生成')
      return this.currentAiScore
    },
    updateRuntime(result) {
      this.snapshot = result.snapshot
      this.currentSession = result.session
      if (result.session?.status !== 'ongoing') {
        this.stopTimer()
      }
    },
    startTimer() {
      this.stopTimer()
      this.timerNow = Date.now()
      this.timerId = window.setInterval(() => {
        this.timerNow = Date.now()
      }, 1000)
    },
    stopTimer() {
      if (this.timerId) {
        window.clearInterval(this.timerId)
        this.timerId = null
      }
    },
  },
})
