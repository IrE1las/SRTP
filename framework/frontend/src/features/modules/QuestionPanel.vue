<template>
  <aside class="question-panel"><span class="eyebrow">一号车站 · 实验一</span><h2>{{ question.title }}</h2><p class="question-prompt">{{ question.public_prompt }}</p><p class="mode-note">{{ mode === 'exam' ? '考核模式：提交后查看分项结果。' : '练习模式：即时记录完成步骤，可另开作答重试。' }}</p><p v-if="feedback" class="live-progress" aria-live="polite">已完成 {{ feedback.completed }} 个操作检查点</p><p v-if="preview" class="mode-note">教师预览 · 不计入学生成绩</p><slot /></aside>
</template>
<script setup>
defineProps({question:Object,mode:String,feedback:Object,preview:Boolean})
</script>
