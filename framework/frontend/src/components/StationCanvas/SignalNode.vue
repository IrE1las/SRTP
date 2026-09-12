<template>
  <g class="signal-node" :class="{ selected: isSelected }" @click.stop="$emit('click', signal.signal_code)">
    <line :x1="stem.x1" :y1="stem.y1" :x2="stem.x2" :y2="stem.y2" class="signal-stem" />
    <circle :cx="signal.position_x" :cy="signal.position_y" r="11" :class="['signal-light', aspect]" />
    <circle v-if="isSelected" :cx="signal.position_x" :cy="signal.position_y" r="18" :class="selectionClass" />
    <text :x="labelX" :y="signal.position_y - 18" class="signal-label">{{ signal.signal_code }}</text>
  </g>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  signal: { type: Object, required: true },
  state: { type: Object, default: () => ({}) },
  selectedRole: { type: String, default: '' },
})

defineEmits(['click'])

const aspect = computed(() => props.state?.aspect || 'closed')
const isSelected = computed(() => Boolean(props.selectedRole))
const selectionClass = computed(() => `selection-ring ${props.selectedRole}`)
const labelX = computed(() => props.signal.position_x - 12)
const stem = computed(() => {
  const offset = props.signal.direction === 'left' ? 18 : -18
  return {
    x1: props.signal.position_x + offset,
    y1: props.signal.position_y + 16,
    x2: props.signal.position_x + offset,
    y2: props.signal.position_y - 16,
  }
})
</script>

<style scoped>
.signal-node {
  cursor: pointer;
}

.signal-stem {
  stroke: #333;
  stroke-width: 3;
}

.signal-light {
  stroke: #333;
  stroke-width: 2;
}

.signal-light.closed {
  fill: #cc0000;
}

.signal-light.open {
  fill: #00cc00;
}

.selection-ring {
  fill: none;
  stroke-width: 3;
  stroke-dasharray: 5 3;
}

.selection-ring.entry {
  stroke: #409eff;
}

.selection-ring.exit {
  stroke: #00c2d1;
}

.signal-label {
  fill: #1f2d3d;
  font-size: 15.4px;
  font-weight: 700;
  user-select: none;
}
</style>
