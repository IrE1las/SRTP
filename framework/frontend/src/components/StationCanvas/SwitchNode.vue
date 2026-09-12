<template>
  <g class="switch-node" @click.stop="$emit('click', switchItem.switch_code, nextPosition)">
    <line :x1="geometry.x" :y1="geometry.y" :x2="activeEnd.x2" :y2="activeEnd.y2" :class="['switch-branch', position]" />
    <circle :cx="geometry.x" :cy="geometry.y" r="8" :class="['switch-point', { locked }]" />
    <text :x="geometry.x - 12" :y="geometry.y - 14" class="switch-label">{{ switchItem.switch_code }}</text>
    <text :x="geometry.x - 10" :y="geometry.y + 26" :class="['switch-position', { locked }]">
      {{ positionLabel }}
    </text>
  </g>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  switchItem: { type: Object, required: true },
  geometry: { type: Object, required: true },
  state: { type: Object, default: () => ({}) },
})

defineEmits(['click'])

const position = computed(() => props.state?.position || props.switchItem.normal_position || 'normal')
const locked = computed(() => Boolean(props.state?.locked))
const activeEnd = computed(() => props.geometry[position.value] || props.geometry.normal)
const nextPosition = computed(() => (position.value === 'normal' ? 'reverse' : 'normal'))
const positionLabel = computed(() => (position.value === 'normal' ? '定' : '反'))
</script>

<style scoped>
.switch-node {
  cursor: pointer;
}

.switch-branch {
  stroke-width: 7;
  stroke-linecap: round;
}

.switch-branch.normal {
  stroke: #333;
}

.switch-branch.reverse {
  stroke: #ffaa00;
}

.switch-point {
  fill: #fff;
  stroke: #333;
  stroke-width: 2;
}

.switch-point.locked {
  fill: #4488ff;
  stroke: #1450bf;
}

.switch-label,
.switch-position {
  fill: #1f2d3d;
  font-size: 13.2px;
  font-weight: 700;
  user-select: none;
}

.switch-position.locked {
  fill: #1450bf;
}
</style>
