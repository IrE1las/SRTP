<template>
  <div class="station-canvas-wrapper">
    <div v-if="stationDetail && snapshot" class="terminal-buttons">
      <span>进路终端：</span>
      <el-button v-for="code in terminalCodes" :key="code" size="small"
        :type="selectedExitSignal === code ? 'primary' : 'default'"
        @click="$emit('signal-click', code)">{{ code }}</el-button>
    </div>
    <svg
      v-if="stationDetail && snapshot"
      class="station-canvas"
      :viewBox="canvas.viewBox"
      role="img"
      aria-label="铁路站场图"
    >
      <rect :width="canvas.width" :height="canvas.height" fill="#eef3f8" rx="18" />

      <g class="section-layer">
        <SectionShape
          v-for="section in stationDetail.sections"
          :key="section.section_code"
          :section-code="section.section_code"
          :segments="sectionShapes[section.section_code] || []"
          :state="snapshot.sections[section.section_code]"
          @click="$emit('section-click', $event)"
        />
      </g>

      <g class="track-layer">
        <line
          v-for="track in trackSegments"
          :key="track.id"
          :x1="track.x1"
          :y1="track.y1"
          :x2="track.x2"
          :y2="track.y2"
          class="track-line"
        />
      </g>

      <g class="route-highlight-layer">
        <template v-for="route in snapshot.active_routes" :key="route.route_name">
          <line
            v-for="segment in routeSegments(route.locked_sections)"
            :key="`${route.route_name}-${segment.x1}-${segment.y1}`"
            :x1="segment.x1"
            :y1="segment.y1"
            :x2="segment.x2"
            :y2="segment.y2"
            class="route-highlight"
          />
        </template>
      </g>

      <g class="switch-layer">
        <SwitchNode
          v-for="switchItem in stationDetail.switches"
          :key="switchItem.switch_code"
          :switch-item="switchItem"
          :geometry="switchGeometry[switchItem.switch_code] || fallbackSwitchGeometry(switchItem)"
          :state="snapshot.switches[switchItem.switch_code]"
          @click="(code, position) => $emit('switch-click', code, position)"
        />
      </g>

      <g class="signal-layer">
        <SignalNode
          v-for="signal in stationDetail.signals"
          :key="signal.signal_code"
          :signal="signal"
          :state="snapshot.signals[signal.signal_code]"
          :selected-role="selectedRole(signal.signal_code)"
          @click="$emit('signal-click', $event)"
        />
      </g>

      <g class="label-layer">
        <text v-for="label in labels" :key="label.text" :x="label.x" :y="label.y" class="track-label">
          {{ label.text }}
        </text>
      </g>
    </svg>
    <el-empty v-else description="正在加载站场图" />
  </div>
</template>

<script setup>
import { computed } from 'vue'

import SectionShape from './SectionShape.vue'
import SignalNode from './SignalNode.vue'
import SwitchNode from './SwitchNode.vue'

const props = defineProps({
  stationDetail: { type: Object, default: null },
  snapshot: { type: Object, default: null },
  selectedEntrySignal: { type: String, default: '' },
  selectedExitSignal: { type: String, default: '' },
})

defineEmits(['signal-click', 'switch-click', 'section-click'])

const config = computed(() => props.stationDetail?.station?.station_config || {})
const canvas = computed(() => config.value.canvas || { width: 1100, height: 420, viewBox: '0 0 1100 420' })
const trackSegments = computed(() => config.value.track_segments || [])
const sectionShapes = computed(() => config.value.section_shapes || {})
const switchGeometry = computed(() => config.value.switch_geometry || {})
const labels = computed(() => config.value.labels || [])
const terminalCodes = computed(() => [...new Set([
  ...(config.value.tracks || []),
  ...(props.stationDetail?.sections || []).filter(item => item.section_type === 'approach').map(item => item.section_code),
])])

function selectedRole(signalCode) {
  if (props.selectedEntrySignal === signalCode) return 'entry'
  if (props.selectedExitSignal === signalCode) return 'exit'
  return ''
}

function routeSegments(sectionCodes) {
  return sectionCodes.flatMap((code) => sectionShapes.value[code] || [])
}

function fallbackSwitchGeometry(switchItem) {
  return {
    x: switchItem.position_x,
    y: switchItem.position_y,
    normal: { x2: switchItem.position_x + 54, y2: switchItem.position_y },
    reverse: { x2: switchItem.position_x + 54, y2: switchItem.position_y - 36 },
  }
}
</script>

<style scoped>
.station-canvas-wrapper {
  width: 100%;
  min-height: 440px;
  padding: 16px;
  overflow: auto;
  background: #dce7f3;
  border: 1px solid #d3dce6;
  border-radius: 12px;
}

.station-canvas {
  width: 100%;
  min-width: 980px;
  height: auto;
}

.track-line {
  stroke: #333;
  stroke-width: 5;
  stroke-linecap: round;
}

.route-highlight {
  stroke: rgba(64, 136, 255, 0.55);
  stroke-width: 22;
  stroke-linecap: round;
  fill: none;
  pointer-events: none;
}

.track-label {
  fill: #1f2d3d;
  font-size: var(--ui-text-lead);
  font-weight: 700;
  user-select: none;
}
</style>
