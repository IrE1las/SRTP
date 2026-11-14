<template>
  <g class="section-shape" @click.stop="$emit('click', sectionCode)">
    <line
      v-for="segment in segments"
      :key="`${sectionCode}-${segment.x1}-${segment.y1}`"
      :x1="segment.x1"
      :y1="segment.y1"
      :x2="segment.x2"
      :y2="segment.y2"
      :class="['section-line', visualState]"
    />
    <text v-if="labelPoint" :x="labelPoint.x" :y="labelPoint.y" class="section-label">{{ sectionCode }}</text>
  </g>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  sectionCode: { type: String, required: true },
  segments: { type: Array, default: () => [] },
  state: { type: Object, default: () => ({}) },
})

defineEmits(['click'])

const visualState = computed(() => {
  if (props.state?.occupancy === 'occupied') return 'occupied'
  if (props.state?.locked) return 'locked'
  return 'clear'
})

const labelPoint = computed(() => {
  const first = props.segments[0]
  if (!first) return null
  return {
    x: (first.x1 + first.x2) / 2 - 14,
    y: (first.y1 + first.y2) / 2 - 10,
  }
})
</script>

<style scoped>
.section-shape {
  cursor: pointer;
}

.section-line {
  fill: none;
  stroke-linecap: round;
  stroke-width: 13;
  opacity: 0.82;
}

.section-line.clear {
  stroke: #fff;
}

.section-line.locked {
  stroke: #4488ff;
}

.section-line.occupied {
  stroke: #ff4444;
}

.section-label {
  fill: #303133;
  font-size: 12.1px;
  font-weight: 700;
  paint-order: stroke;
  stroke: #fff;
  stroke-width: 3px;
  user-select: none;
}
</style>
