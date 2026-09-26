<template>
  <svg class="station-diagram" viewBox="0 0 1920 870" preserveAspectRatio="xMidYMid meet"
    role="img" aria-label="联锁测试站全站站场和可操作按钮">
    <rect width="1920" height="870" fill="#05090e" />
    <text v-for="label in station.labels" :key="label.text"
      :x="labelX(label)" :y="labelY(label)"
      :class="label.text === station.station_name ? 'station-title' : 'direction-label'"
      :style="{ writingMode: label.orientation === 1 ? 'vertical-rl' : undefined }">{{ label.text }}</text>

    <g class="section-layer">
      <g v-for="section in station.sections" :key="section.id" class="section-item"
        tabindex="0" role="button" :aria-label="`${section.name} 区段，${sectionText(section.name)}`"
        @click="emit('inspect', '区段', section.name, sectionText(section.name))"
        @keydown.enter="emit('inspect', '区段', section.name, sectionText(section.name))">
        <line :x1="section.draw_x1" :y1="section.y1" :x2="section.draw_x2" :y2="section.y2"
          :stroke="sectionColor(section.name)" stroke-width="5" stroke-linecap="round" />
        <line :x1="section.draw_x1" :y1="section.y1" :x2="section.draw_x2" :y2="section.y2"
          stroke="transparent" stroke-width="22" />
        <text :x="section.label_x" :y="section.label_y" text-anchor="middle" class="section-label">
          {{ section.name }}
        </text>
        <title>{{ section.name }}：{{ sectionText(section.name) }}</title>
      </g>
    </g>

    <g class="switch-layer">
      <g v-for="point in station.switches" :key="point.id" tabindex="0" role="button"
        :aria-label="`${point.name} 号道岔，${switchText(point.id)}`"
        @click="emit('inspect', '道岔', point.name, switchText(point.id))"
        @keydown.enter="emit('inspect', '道岔', point.name, switchText(point.id))">
        <line :x1="point.draw_front_x" :y1="point.front_y" :x2="point.x" :y2="point.y"
          :stroke="sectionColor(point.section)" stroke-width="5" stroke-linecap="round" />
        <line :x1="point.x" :y1="point.y" :x2="point.draw_back_x" :y2="point.back_y"
          :stroke="sectionColor(point.section)" stroke-width="5" stroke-linecap="round" />
        <polyline :points="`${point.x},${point.y} ${point.break_x},${point.break_y} ${point.branch_x},${point.branch_y}`"
          fill="none" :stroke="sectionColor(point.section)" stroke-width="5" stroke-linecap="round" stroke-linejoin="round" />
        <line :x1="blade(point).x1" :y1="blade(point).y1" :x2="blade(point).x2" :y2="blade(point).y2"
          :stroke="bladeColor(point.id)" stroke-width="7" stroke-linecap="butt" />
        <circle :cx="point.x" :cy="point.y" r="10" fill="transparent" stroke="none" />
        <text :x="point.x" :y="point.y - 9" text-anchor="middle" class="switch-label"
          :class="{ reverse: snapshot?.switches?.[point.id]?.position === 1 }">{{ point.name }}</text>
        <title>{{ point.name }} 号道岔：{{ switchText(point.id) }}</title>
      </g>
    </g>

    <g class="insulation-layer" aria-label="轨道绝缘节与侵限绝缘">
      <g v-for="(joint, index) in station.boundaries" :key="index" :transform="`translate(${joint.x},${joint.y})`">
        <line v-if="joint.shape === 2" x1="0" y1="-10" x2="0" y2="10" class="insulation-mark" />
        <line v-else-if="joint.shape === 0" x1="-8" y1="-4" x2="8" y2="4" class="insulation-mark" />
        <line v-else-if="joint.shape === 1" x1="-8" y1="4" x2="8" y2="-4" class="insulation-mark" />
        <line v-else x1="-10" y1="0" x2="10" y2="0" class="insulation-mark" />
        <circle v-if="joint.infringing" r="7" class="infringing-mark" />
      </g>
    </g>

    <g class="signal-layer">
      <g v-for="signal in station.signals" :key="signal.id" :transform="`translate(${signal.x},${signal.y})`"
        class="signal-item" :class="{ clickable: shuntButton(signal.name) }"
        :tabindex="shuntButton(signal.name) ? 0 : undefined"
        :role="shuntButton(signal.name) ? 'button' : undefined"
        :aria-label="signalAria(signal)"
        @click="onSignalClick(signal)"
        @keydown.enter="onSignalClick(signal)">
        <line x1="0" y1="0" x2="0" :y2="signalSide(signal) * 23" stroke="#6c9dc8" stroke-width="3" />
        <line v-if="signal.model === 0 || signal.model === 2" x1="-5" :y1="signalSide(signal) * 8" x2="5" :y2="signalSide(signal) * 8"
          stroke="#6c9dc8" stroke-width="2" />
        <circle :cx="nearX(signal)" :cy="signalSide(signal) * 23" r="8" :fill="lampColor(signal, 'near')"
          stroke="#87a5c3" stroke-width="1.5" />
        <circle v-if="signal.model < 2" :cx="farX(signal)" :cy="signalSide(signal) * 23" r="8"
          :fill="lampColor(signal, 'far')" stroke="#87a5c3" stroke-width="1.5" />
        <rect x="-39" :y="signalSide(signal) < 0 ? -45 : -8" width="78" height="54" fill="transparent" />
        <text x="0" :y="signalSide(signal) < 0 ? -39 : 46" text-anchor="middle" class="signal-label">{{ signal.name }}</text>
        <title>{{ signal.name }}：{{ signalAspectText(signal) }}{{ shuntButton(signal.name) ? `；点击选择 ${shuntButton(signal.name)}` : '' }}</title>
      </g>
    </g>

    <g class="button-layer">
      <g v-for="button in visibleButtons" :key="button.id" :transform="`translate(${button.drawX},${button.drawY})`"
        class="station-button" :class="{ disabled: button.type === 0 || button.type === 1,
          selected: selected.includes(button.name) }"
        tabindex="0" role="button" :aria-label="`${button.name}，${buttonPurpose(button)}`"
        @click="onButtonClick(button)" @keydown.enter="onButtonClick(button)">
        <rect x="-9" y="-9" width="18" height="18" rx="1"
          :fill="buttonFill(button)" :stroke="selected.includes(button.name) ? '#ffd950' : '#86aec6'"
          stroke-width="2" />
        <text v-if="selected.includes(button.name) || button.type === 4" x="0" y="-16"
          text-anchor="middle" class="button-label">{{ button.name }}</text>
        <title>{{ button.name }}：{{ buttonPurpose(button) }}</title>
      </g>
    </g>

    <g class="switch-button-layer">
      <g v-for="item in station.switch_buttons" :key="item.name"
        :transform="`translate(${item.x},${item.y + 75})`" class="switch-button">
        <rect x="-26" y="-13" width="52" height="26" rx="3" fill="#152534" stroke="#426889" />
        <text x="0" y="5" text-anchor="middle">{{ item.name }}</text>
        <title>{{ item.name }} 道岔组，第一阶段仅显示位置，不提供单独操纵</title>
      </g>
    </g>
  </svg>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  station: { type: Object, required: true },
  snapshot: { type: Object, default: null },
  selected: { type: Array, default: () => [] },
})
const emit = defineEmits(['press', 'inspect', 'disabled'])

const shuntNames = computed(() => Object.fromEntries(props.station.buttons
  .filter(button => button.type === 3 && button.signal)
  .map(button => [button.signal, button.name])))
const visibleButtons = computed(() => {
  const buttons = props.station.buttons.filter(button => button.type !== 3)
  const groups = new Map()
  buttons.forEach(button => {
    const key = `${button.x}:${button.y}`
    groups.set(key, [...(groups.get(key) || []), button.name])
  })
  return buttons.map(button => {
    const names = groups.get(`${button.x}:${button.y}`)
    const index = names.indexOf(button.name)
    return { ...button, drawX: button.x + (index - (names.length - 1) / 2) * 24,
      drawY: button.y }
  })
})

function shuntButton(name) { return shuntNames.value[name] }
function onSignalClick(signal) {
  const button = shuntButton(signal.name)
  if (button) emit('press', button)
  else emit('inspect', '信号机', signal.name, signalAspectText(signal))
}
function onButtonClick(button) {
  if (button.type === 0 || button.type === 1) emit('disabled', `${button.name} 属于通过或引导进路，本阶段未开放`)
  else emit('press', button.name)
}
function buttonPurpose(button) {
  return button.type === 2 ? '列车按钮' : button.type === 4 ? '变通按钮' : '本阶段未开放'
}
function buttonFill(button) {
  if (props.selected.includes(button.name)) return '#e5b94c'
  return button.type === 2 ? '#145831' : button.type === 4 ? '#9da8ae' : '#4d565e'
}
function sectionColor(name) {
  const state = props.snapshot?.sections?.[name]
  return state?.occupied ? '#f04448' : state?.locked ? '#f3f4f4' : '#5b83b1'
}
function sectionText(name) {
  const state = props.snapshot?.sections?.[name]
  return state?.occupied ? '占用' : state?.locked ? '进路锁闭' : '空闲'
}
function bladeColor(id) { return props.snapshot?.switches?.[id]?.position === 1 ? '#f4ca47' : '#65e344' }
function blade(point) {
  const reverse = props.snapshot?.switches?.[point.id]?.position === 1
  const dx = reverse ? point.break_x - point.x : point.back_x - point.front_x
  const dy = reverse ? point.break_y - point.y : point.back_y - point.front_y
  const length = Math.hypot(dx, dy) || 1
  const ux = dx / length
  const uy = dy / length
  return { x1: point.x - ux * 12, y1: point.y - uy * 12,
    x2: point.x + ux * 12, y2: point.y + uy * 12 }
}
function switchText(id) {
  const state = props.snapshot?.switches?.[id]
  return `${state?.position === 1 ? '反位' : '定位'}，${state?.locked ? '锁闭' : '未锁闭'}`
}
function signalSide(signal) { return signal.orientation === 1 || signal.orientation === 2 ? 1 : -1 }
function nearX(signal) { return signalSide(signal) < 0 ? 8 : -8 }
function farX(signal) { return signalSide(signal) < 0 ? 25 : -25 }
function labelX(label) {
  if (label.text === '联锁测试站') return 900
  if (label.orientation === 1) return label.x < 960 ? 18 : 1883
  return label.x
}
function labelY(label) { return label.text === '联锁测试站' ? label.y + 12 : label.y }
function lampColor(signal, which) {
  const aspect = props.snapshot?.signals?.[signal.name]?.aspect
  if (signal.model >= 2) return aspect === 'B' ? '#f1f5ef' : '#2354c6'
  if (!aspect) return which === 'near' ? '#e2393e' : '#05090e'
  if (aspect === 'UU') return '#f3cc25'
  if (aspect === 'U') return which === 'far' ? '#f3cc25' : '#05090e'
  if (aspect === 'L') return which === 'far' ? '#35ca62' : '#05090e'
  if (aspect === 'B') return which === 'near' ? '#f1f5ef' : '#05090e'
  return '#05090e'
}
function signalAspectText(signal) {
  const aspect = props.snapshot?.signals?.[signal.name]?.aspect
  return aspect ? `开放显示 ${aspect}` : (signal.type === 2 ? '禁止调车，蓝灯' : '关闭，红灯')
}
function signalAria(signal) {
  return `${signal.name} 信号机，${signalAspectText(signal)}${shuntButton(signal.name) ? `，点击选择 ${shuntButton(signal.name)}` : ''}`
}
</script>

<style scoped>
.station-diagram { display: block; width: 100%; height: 100%; min-width: 930px; background: #05090e; }
.station-title { fill: #eaf1f6; font: 30px "STKaiti", "KaiTi", serif; letter-spacing: 5px; }
.direction-label { fill: #aab6c3; font: 14px "Microsoft YaHei", sans-serif; }
.section-item, .switch-layer g { cursor: help; }
.insulation-mark { stroke: #aebbc3; stroke-width: 2.2; stroke-linecap: square; }
.infringing-mark { fill: none; stroke: #ed404c; stroke-width: 2.5; }
.section-label { fill: #aab8c9; font: 13px Georgia, "Microsoft YaHei", serif; pointer-events: none; }
.switch-label { fill: #65e344; font: bold 13px Georgia, serif; pointer-events: none; }
.switch-label.reverse { fill: #f4ca47; }
.signal-label { fill: #dce7ef; font: 13px Georgia, serif; pointer-events: none; }
.signal-item.clickable { cursor: pointer; }
.signal-item.clickable:hover circle, .station-button:hover rect { filter: drop-shadow(0 0 5px #f5cf55); }
.station-button { cursor: pointer; }
.station-button.disabled { cursor: not-allowed; opacity: .65; }
.button-label { fill: #e9eff5; font: 11px Georgia, serif; pointer-events: none; }
.switch-button text { fill: #b6c5d3; font: 13px Georgia, serif; }
.station-diagram [tabindex="0"]:focus-visible { outline: none; filter: drop-shadow(0 0 8px #f5cf55); }
</style>
