<template>
  <el-card shadow="never">
    <template #header>
      <strong>{{ isEdit ? '编辑练习' : '新建练习' }}</strong>
    </template>

    <el-form ref="formRef" :model="form" :rules="rules" label-width="100px" class="editor-form">
      <el-form-item label="题目标题" prop="title">
        <el-input v-model="form.title" />
      </el-form-item>
      <el-form-item label="题目说明" prop="description">
        <el-input v-model="form.description" type="textarea" :rows="4" />
      </el-form-item>
      <el-form-item label="目标进路">
        <el-space>
          <el-input v-model="target.entry_signal" placeholder="始端，如 X" style="width: 100px" />
          <span>→</span>
          <el-input v-model="target.exit_signal" placeholder="终端，如 I" style="width: 100px" />
          <el-input v-model="target.route_name" placeholder="进路名称" style="width: 220px" />
        </el-space>
      </el-form-item>
      <el-form-item label="限时" prop="time_limit">
        <el-input-number v-model="form.time_limit" :min="30" :max="7200" /> 秒
      </el-form-item>
      <el-form-item label="难度" prop="difficulty">
        <el-select v-model="form.difficulty" style="width: 180px">
          <el-option label="简单" value="easy" />
          <el-option label="中等" value="medium" />
          <el-option label="困难" value="hard" />
        </el-select>
      </el-form-item>
      <el-form-item label="发布状态">
        <el-switch v-model="form.is_active" active-text="发布" inactive-text="停用" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleSave">保存</el-button>
        <el-button @click="router.push('/teacher/exercises')">返回</el-button>
      </el-form-item>
    </el-form>
  </el-card>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useExerciseStore } from '@/store/exercise'

const route = useRoute()
const router = useRouter()
const store = useExerciseStore()
const formRef = ref()
const isEdit = computed(() => Boolean(route.params.id))

const form = reactive({
  title: '办理 X 至 I 道接车进路',
  description: '请在标准站场中办理 X 至 I 道接车进路。',
  exercise_type: 'route_arrange',
  time_limit: 600,
  difficulty: 'easy',
  is_active: true,
  scoring_rules: {},
})

const target = reactive({
  entry_signal: 'X',
  exit_signal: 'I',
  route_name: 'X至I道接车进路',
})

const rules = {
  title: [{ required: true, message: '请输入题目标题', trigger: 'blur' }],
  time_limit: [{ required: true, message: '请输入限时', trigger: 'change' }],
}

onMounted(async () => {
  if (!isEdit.value) return
  const exercise = await store.loadExercise(route.params.id)
  Object.assign(form, {
    title: exercise.title,
    description: exercise.description,
    exercise_type: exercise.exercise_type,
    time_limit: exercise.time_limit,
    difficulty: exercise.difficulty,
    is_active: exercise.is_active,
    scoring_rules: exercise.scoring_rules || {},
  })
  Object.assign(target, exercise.target_routes?.[0] || target)
})

async function handleSave() {
  await formRef.value.validate()
  await store.saveExercise(
    {
      ...form,
      target_routes: [{ ...target }],
    },
    route.params.id || null,
  )
  router.push('/teacher/exercises')
}
</script>

<style scoped>
.editor-form {
  max-width: 760px;
}
</style>
