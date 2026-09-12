<template>
  <section class="station-board" :aria-label="referenceMode ? '实验专题完整站场' : '经典例题完整站场'">
    <div class="board-toolbar">
      <div><span class="live-dot"></span><strong>{{ referenceMode ? '原图站场 · 读图定位' : '站场操作图' }}</strong><span class="board-subtitle">{{ referenceMode ? '圈定范围全图 · 实验专题共用' : '铅笔圈内全图 · 四题共用' }}</span></div>
      <div class="zoom-tools">
        <button type="button" aria-label="缩小站场" @click="zoomBy(1 / 1.25)">−</button>
        <span>{{ Math.round(zoom * 100) }}%</span>
        <button type="button" aria-label="放大站场" @click="zoomBy(1.25)">＋</button>
        <button type="button" @click="fit">全图</button>
      </div>
    </div>
    <div class="canvas-frame">
      <svg ref="svg" class="classic-station" :viewBox="viewBox" aria-label="下行咽喉站场交互图" @pointerdown="startPan" @pointermove="movePan" @pointerup="endPan" @pointercancel="endPan" @wheel.ctrl.prevent="onWheel">
        <defs>
          <pattern id="classic-grid" width="28" height="28" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="0.8" fill="#314354" /></pattern>
          <marker id="direction-arrow" markerWidth="8" markerHeight="8" refX="5" refY="3" orient="auto"><path d="M0 0L6 3L0 6" fill="none" stroke="#94aabd" /></marker>
        </defs>
        <rect x="-1700" y="-830" width="5100" height="2490" fill="#111e2b" />
        <rect x="0" y="0" :width="canvasSize.width" :height="canvasSize.height" fill="url(#classic-grid)" />
        <text x="42" y="45" class="diagram-caption">下行咽喉 · 设备平面布置</text>
        <text x="1650" y="45" text-anchor="end" class="diagram-note">{{ referenceMode ? '点击设备定位 · 拖动空白处平移 · Ctrl + 滚轮缩放' : '点击设备作答 · 拖动空白处平移 · Ctrl + 滚轮缩放' }}</text>
        <text x="50" y="219" class="direction-label">东郊方面</text>
        <path d="M55 235H155" class="direction-line" marker-end="url(#direction-arrow)" />
        <text x="50" y="423" class="direction-label">北京方面</text>
        <path d="M55 444H155" class="direction-line" marker-end="url(#direction-arrow)" />
        <path d="M165 653H60" class="direction-line" marker-end="url(#direction-arrow)" />

        <g v-for="track in tracks" :key="track.id" class="base-track">
          <line :x1="track.start" :y1="track.y" :x2="track.end" :y2="track.y" />
          <text :x="1633" :y="track.y - 42" text-anchor="middle">{{ track.id }} 股道</text>
        </g>
        <g v-for="sec in sections" :key="sec.name" class="section-hit interactive" :class="{ chosen: answer.track_sections.includes(sec.name), 'has-error': hasError('track_sections', sec.name), focused: isFocused('track_sections', sec.name) }"
          :data-code="sec.name" role="button" tabindex="0" :aria-label="`轨道区段 ${sec.name}`" :aria-pressed="answer.track_sections.includes(sec.name)" @click.stop="sectionClick(sec.name)" @keydown.enter.prevent="sectionClick(sec.name)" @keydown.space.prevent="sectionClick(sec.name)">
          <title>{{ sec.name }}：点击选择或取消检查区段</title>
          <g v-for="(p, i) in sec.segments" :key="i">
            <line :x1="p[0]" :y1="p[1]" :x2="p[2]" :y2="p[3]" class="section-selection" />
            <line :x1="p[0]" :y1="p[1]" :x2="p[2]" :y2="p[3]" class="section-rail" />
            <line :x1="p[0]" :y1="p[1]" :x2="p[2]" :y2="p[3]" class="section-touch" />
          </g>
          <rect :x="sec.x - Math.max(sec.name.length * 6, 28)" :y="sec.labelY - 17" :width="Math.max(sec.name.length * 12, 56)" height="27" rx="5" class="section-label-bg" />
          <text :x="sec.x" :y="sec.labelY + 2" text-anchor="middle" class="section-label">{{ sec.name }}</text>
        </g>
        <g class="boundaries" aria-hidden="true">
          <line v-for="sec in sections" :key="sec.name" :data-section="sec.name"
            :x1="mapX(sec.x_start)" :x2="mapX(sec.x_start)" :y1="sec.y - 7" :y2="sec.y + 7" />
        </g>

        <g v-for="sw in switches" :key="sw.id" class="switch-hit interactive" :data-code="sw.id" :class="[answer.switches[sw.id], { 'has-error': hasError('switches', sw.id), focused: isFocused('switches', sw.id) }]"
          role="button" tabindex="0" :aria-label="`道岔 ${sw.id}`" @click.stop="$emit('inspect', 'switches', sw.id)" @keydown.enter.prevent="$emit('inspect', 'switches', sw.id)" @keydown.space.prevent="$emit('inspect', 'switches', sw.id)">
          <title>{{ sw.id }} 号道岔：{{ positionLabel(answer.switches[sw.id]) }}，点击设置</title>
          <path v-if="answer.switches[sw.id] === 'reverse'" :d="`M${sw.a.x} ${sw.a.y}L${sw.b.x} ${sw.b.y}`" class="switch-connection" />
          <g v-for="(p, i) in sw.switch_b ? [sw.a, sw.b] : [sw.a]" :key="i">
            <circle :cx="p.x" :cy="p.y" r="18" class="switch-target" />
            <path :d="`M${p.x - 9} ${p.y}h18`" class="switch-symbol" :transform="answer.switches[sw.id] === 'reverse' ? `rotate(${sw.b.y > sw.a.y ? 45 : -45} ${p.x} ${p.y})` : undefined" />
            <text :x="p.x + (['1', '5', '17'].includes(p.label) ? 24 : 0)" :y="p.y - 26" text-anchor="middle" class="switch-number">{{ p.label }}</text>
            <text v-if="answer.switches[sw.id]" :x="p.x" :y="p.y + 6" text-anchor="middle" class="switch-position">{{ answer.switches[sw.id] === 'normal' ? '定' : '反' }}</text>
          </g>
        </g>

        <g v-for="sig in signals" :key="sig.name">
          <g class="signal-hit interactive" :class="{ chosen: signalChosen(sig), hostile: answer.hostile_signals.includes(sig.name) || answer.hostile_signals.includes(sig.shuntFunction), 'has-error': signalError(sig), focused: isFocused('signals', sig.name) || isFocused('signals', sig.shuntFunction) }" :data-code="sig.name"
            :transform="`translate(${sig.x}, ${sig.y})`" role="button" tabindex="0" :aria-label="`信号机 ${sig.name}`" @click.stop="$emit('inspect', 'signals', sig.name)" @keydown.enter.prevent="$emit('inspect', 'signals', sig.name)" @keydown.space.prevent="$emit('inspect', 'signals', sig.name)">
            <title>{{ sig.name }} {{ sig.type }}信号机：点击选择按钮或标记敌对{{ sig.shuntFunction ? `；调车功能 ${sig.shuntFunction} 在同一操作面板中选择` : '' }}</title>
            <rect :x="sig.hitbox.x" :y="sig.hitbox.y" :width="sig.hitbox.width" :height="sig.hitbox.height" class="signal-hitbox" />
            <RailwaySignalSymbol :variant="sig.symbol" :direction="sig.direction" />
            <text :x="sig.direction === 1 ? -9 : 18" y="5" :text-anchor="sig.direction === 1 ? 'end' : 'start'" class="signal-code"><tspan>{{ sig.name[0] }}</tspan><tspan v-if="sig.name.length > 1" baseline-shift="sub" font-size="16.5">{{ sig.name.slice(1) }}</tspan></text>
          </g>
        </g>

        <g class="terminal-hit interactive" :class="{ chosen: answer.route_buttons.includes('SLZA'), 'has-error': hasError('route_buttons', 'SLZA'), focused: isFocused('route_buttons', 'SLZA') }" data-code="SLZA" role="button" tabindex="0" aria-label="发车终端按钮 SLZA" :aria-pressed="answer.route_buttons.includes('SLZA')" @click.stop="terminalClick" @keydown.enter.prevent="terminalClick" @keydown.space.prevent="terminalClick">
          <rect x="72" y="675" width="168" height="46" rx="8" /><text x="156" y="704" text-anchor="middle">SLZA · 发车终端</text>
        </g>
        <g class="reference-hit interactive" :class="{ hostile: answer.hostile_signals.includes(photoSignalCode), 'has-error': hasError('hostile_signals', photoSignalCode), focused: isFocused('reference', photoSignalCode) }" :data-code="photoSignalCode" role="button" tabindex="0" aria-label="原图预告信号" @click.stop="$emit('inspect', 'reference', photoSignalCode)" @keydown.enter.prevent="$emit('inspect', 'reference', photoSignalCode)" @keydown.space.prevent="$emit('inspect', 'reference', photoSignalCode)">
          <title>原图标注 Y_XD 的预告信号：点击作答</title>
          <rect :x="photoSignalPosition.x - 56" :y="photoSignalPosition.y - 13" width="118" height="26" class="signal-hitbox" />
          <g :transform="`translate(${photoSignalPosition.x} ${photoSignalPosition.y})`"><RailwaySignalSymbol variant="YXD" :direction="1" /><text x="-9" y="5" text-anchor="end" class="signal-code"><tspan>Y</tspan><tspan baseline-shift="sub" font-size="16.5">XD</tspan></text></g>
        </g>
      </svg>
    </div>
    <div v-if="referenceMode" class="board-legend"><span>点击设备可定位并核对名称；作答请填写下方各栏。图中颜色不代表仿真运行或真实设备状态。</span></div>
    <div v-else class="board-legend"><span><i class="legend-blue"></i>已选按钮 / 检查区段</span><span><i class="legend-purple"></i>已选敌对信号</span><span><b class="legend-normal">定</b>道岔定位</span><span><b class="legend-reverse">反</b>道岔反位</span><span><i class="legend-error"></i>提交后错误定位</span><span class="legend-note">颜色表示作答状态</span></div>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import RailwaySignalSymbol from './RailwaySignalSymbol.vue'
import { canvasSize, tracks, switches, signals, sections, mapX, devicePosition, photoSignalCode, photoSignalPosition } from '@/domain/classicStation'
const props = defineProps({ answer: { type: Object, required: true }, errors: { type: Array, default: () => [] }, focus: { type: Object, default: null }, referenceMode: { type: Boolean, default: false } })
const emit = defineEmits(['inspect', 'toggle-section', 'toggle-hostile', 'toggle-button'])
const svg = ref(null), zoom = ref(1), center = ref({ x: 850, y: 415 })
const viewBox = computed(() => `${center.value.x - 850 / zoom.value} ${center.value.y - 415 / zoom.value} ${1700 / zoom.value} ${830 / zoom.value}`)
function fit() { zoom.value = 1; center.value = { x: 850, y: 415 } }
function zoomBy(factor) { zoom.value = Math.max(1, Math.min(3, zoom.value * factor)); clampCenter() }
function clampCenter() { const hx = 850 / zoom.value, hy = 415 / zoom.value; center.value = { x: Math.max(hx, Math.min(1700 - hx, center.value.x)), y: Math.max(hy, Math.min(830 - hy, center.value.y)) } }
function locate(kind, code) { const p = devicePosition(kind, code); if (p) { zoom.value = 1.5; center.value = { x: p.x, y: p.y }; clampCenter() } }
defineExpose({ fit, locate })
function onWheel(event) { zoomBy(event.deltaY < 0 ? 1.12 : 1 / 1.12) }
let pan = null
function startPan(e) { if (e.button !== 0 || e.target.closest('.interactive')) return; pan = { x: e.clientX, y: e.clientY, center: { ...center.value } }; svg.value.setPointerCapture(e.pointerId) }
function movePan(e) { if (!pan) return; const bounds = svg.value.getBoundingClientRect(); const scale = 1700 / zoom.value / bounds.width; center.value = { x: pan.center.x - (e.clientX - pan.x) * scale, y: pan.center.y - (e.clientY - pan.y) * scale }; clampCenter() }
function endPan() { pan = null }
function hasError(kind, code) { return props.errors.some(e => e.kind === kind && e.code === code) }
function isFocused(kind, code) { return props.focus?.kind === kind && props.focus?.code === code }
function signalChosen(sig) { return sig.buttons.some(b => props.answer.route_buttons.includes(b)) }
function signalError(sig) { return hasError('hostile_signals', sig.name) || hasError('hostile_signals', sig.shuntFunction) || sig.buttons.some(b => hasError('route_buttons', b)) }
function positionLabel(p) { return p === 'normal' ? '定位' : p === 'reverse' ? '反位' : '未作答' }
function sectionClick(code) { emit('inspect', 'track_sections', code); emit('toggle-section', code) }
function terminalClick() { emit('inspect', 'route_buttons', 'SLZA'); emit('toggle-button', 'SLZA') }
</script>

<style scoped>
.station-board { overflow: hidden; border-radius: 15px; border: 1px solid #283f53; background: #111e2b; box-shadow: 0 10px 28px #172c4512; }
.board-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 16px 20px; background: #192b3c; color: #e9f3fb; }
.board-subtitle { font-size: var(--ui-text-base); margin-left: 16px; color: #b2c6d7; }
.live-dot { display: inline-block; width: 7px; height: 7px; margin-right: 10px; background: #5bcbba; border-radius: 50%; }
.zoom-tools { display: flex; align-items: center; gap: 8px; font-size: var(--ui-text-base); }
.zoom-tools button { background: #233c52; border: 1px solid #3b5369; color: #e9f3fb; border-radius: 5px; padding: 4px 9px; cursor: pointer; }
.classic-station { display: block; width: 100%; aspect-ratio: 1700 / 830; touch-action: none; user-select: none; }
.canvas-frame { overflow: hidden; }
svg text { font-family: 'Microsoft YaHei', sans-serif; }
.diagram-caption { fill: #b9cddd; font-size: 20.9px; font-weight: 700; }
.diagram-note { fill: #8ca6bb; font-size: 16.5px; }
.direction-label { fill: #d1dfeb; font-size: 23.1px; font-weight: 700; }
.direction-line { stroke: #94aabd; fill: none; stroke-width: 2; }
.base-track line { stroke: #8c9aa7; stroke-width: 4; }
.base-track text { fill: #c8d8e6; font-size: 24.2px; font-weight: 700; }
.section-rail { stroke: #9baab8; stroke-width: 4; }
.section-selection { stroke: transparent; stroke-width: 16; }
.section-touch { stroke: transparent; stroke-width: 23; }
.section-label-bg { fill: #172b3d; stroke: transparent; }
.section-label { fill: #aec6d9; font-size: 19.8px; }
.section-hit.chosen .section-selection { stroke: #238fd766; }
.section-hit.chosen .section-rail { stroke: #67c4ff; }
.section-hit.chosen .section-label-bg { fill: #134e73; stroke: #5bbdff; }
.section-hit.chosen .section-label { fill: #ecf7ff; }
.boundaries { stroke: #e3edf5; stroke-width: 2; pointer-events: none; }
.switch-target { fill: #1c3043; stroke: #c4d4e0; stroke-width: 2; }
.switch-symbol { stroke: #dce7ef; stroke-width: 3; }
.switch-number { fill: #edf3f7; font-size: 22px; font-weight: 700; paint-order: stroke; stroke: #111e2b; stroke-width: 6; }
.switch-position { fill: #092a30; font-size: 17.6px; font-weight: 700; }
.switch-hit.normal .switch-target { fill: #67d5bf; stroke: #a3f1df; }
.switch-hit.reverse .switch-target { fill: #f4c779; stroke: #ffe4b6; }
.switch-hit.normal .switch-symbol, .switch-hit.reverse .switch-symbol { display: none; }
.switch-connection { stroke: #f4c779; stroke-width: 5; stroke-dasharray: 9 5; opacity: .9; pointer-events: none; }
.signal-hitbox { fill: transparent; stroke: transparent; stroke-width: 1.5; }
.signal-code { fill: #e2ebf2; font-family: 'Times New Roman', serif; font-size: 27.5px; pointer-events: none; }
.signal-hit.chosen > .signal-hitbox { stroke: #65c3ff; stroke-dasharray: 4 3; }
.signal-hit.hostile > .signal-hitbox, .reference-hit.hostile > .signal-hitbox { stroke: #c6a1ff; stroke-dasharray: 4 3; }
.terminal-hit rect { fill: #233a4e; stroke: #6e889f; stroke-width: 1.5; }
.terminal-hit text { fill: #e3edf7; font-size: 21px; font-weight: 600; }
.terminal-hit.chosen rect { fill: #15557c; stroke: #65c3ff; stroke-width: 3; }
.interactive { cursor: pointer; outline: none; }
.interactive:hover > rect, .interactive:focus-visible > rect, .interactive.focused > rect { stroke: #fff; stroke-width: 3; }
.switch-hit:hover .switch-target, .switch-hit:focus-visible .switch-target, .switch-hit.focused .switch-target { stroke: white; stroke-width: 4; }
.section-hit:hover .section-label-bg, .section-hit:focus-visible .section-label-bg, .section-hit.focused .section-label-bg { stroke: white; stroke-width: 2; }
.has-error > rect, .has-error .switch-target, .has-error .section-label-bg { stroke: #ff917e !important; stroke-width: 3 !important; stroke-dasharray: 5 3; }
.has-error .section-selection { stroke: #ff816342; }
.board-legend { display: flex; align-items: center; flex-wrap: wrap; gap: 12px 20px; padding: 12px 20px; border-top: 1px solid #2a4053; color: #c3d1df; font-size: var(--ui-text-base); }
.board-legend span { display: flex; align-items: center; gap: 6px; }
.board-legend i { display: inline-block; width: 9px; height: 9px; border-radius: 2px; }
.legend-blue { background: #5bbdff; }.legend-purple { background: #c6a1ff; }.legend-error { border: 1px dashed #ff917e; }.legend-normal { color: #67d5bf; }.legend-reverse { color: #f4c779; }.legend-note { margin-left: auto; color: #91aabd; }
@media (max-width: 1150px) { .board-subtitle { display: none; } }
</style>
