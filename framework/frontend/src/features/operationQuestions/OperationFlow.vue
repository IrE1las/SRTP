<template>
  <div class="op-flow">
    <router-link class="op-back" :to="backTo">← {{ backLabel }}</router-link>
    <header class="op-heading"><div><h1>{{ title }}</h1><p class="op-muted">{{ subtitle }}</p></div><slot /></header>
    <el-steps :active="step" finish-status="success" simple aria-label="出题流程">
      <el-step title="题目设置" /><el-step title="录制答案" /><el-step title="检查发布" />
    </el-steps>
  </div>
</template>
<script setup>
import './operation.css'
defineProps({ step: { type: Number, required: true }, title: { type: String, required: true }, subtitle: { type: String, default: '' }, backTo: { type: [String, Object], default: '/operations/manage' }, backLabel: { type: String, default: '操作题库' } })
</script>
