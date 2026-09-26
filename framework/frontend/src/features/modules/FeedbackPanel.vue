<template>
  <section v-if="result" class="feedback-panel"><h2>操作反馈 <span>{{ result.score }} 分</span></h2><p>文字说明已保存，不计入自动评分。</p><article v-for="c in result.checkpoints" :key="c.number" :class="['checkpoint', {passed:c.passed}]"><div><strong>{{ c.number }}. {{ c.label }}</strong><span>{{ c.passed ? '通过' : '待纠正' }} · {{ c.points }}/{{ c.possible }}</span></div><p>{{ c.message }}</p><p v-if="c.correction">{{ c.correction }}</p><button v-if="c.event_id" @click="emit('locate',c)">定位操作与设备 →</button></article></section>
</template>
<script setup>
defineProps({result:Object})
const emit=defineEmits(['locate'])
</script>
