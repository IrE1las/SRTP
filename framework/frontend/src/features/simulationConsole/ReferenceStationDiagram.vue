<template>
  <svg class="reference-diagram" viewBox="0 0 1440 740" fill="#c0c0c0" role="group" aria-label="标准站全站联锁操作图">
    <rect width="1440" height="740" :fill="C.background" />
    <text x="630" y="68" class="station-title">标准站</text>
    <g v-for="record in tracks" :key="record.offset" tabindex="0" role="button"
      :aria-label="`${record.name} 区段`" @click="inspectSection(record.name)" @keydown.enter="inspectSection(record.name)">
      <polyline :points="poly(record.points)" :stroke="color(record.name)" class="track" />
      <polyline :points="poly(record.points)" stroke="transparent" stroke-width="18" fill="none" />
      <rect :x="record.label[0]-4" :y="record.label[1]-18" :width="record.name.length*9+8" height="22" fill="transparent" />
      <text :x="record.label[0]" :y="record.label[1]" class="section-label">{{ record.name }}</text>
      <text v-if="snapshot?.fault_releases?.[record.name]" :x="record.label[0]" :y="record.label[1]+17" fill="red">区故解 {{ snapshot.fault_releases[record.name] }} 秒</text>
      <title>{{ record.name }}：{{ sectionText(record.name) }}</title>
    </g>
    <g v-for="point in station.switches" :key="point.id" :data-switch="point.id">
      <polyline v-for="(branch, index) in point.geometry.branches" :key="index"
        :points="poly([point.geometry.point, ...branch])" :stroke="branchColor(point, index)" class="track" />
      <template v-if="lostIndication(point.id)">
        <line v-for="branch in [1,2]" :key="branch" v-bind="blade(point, branch, 1, 11)"
          :stroke="C.red" stroke-width="5" class="blade-flash" />
      </template>
      <template v-else>
        <line v-bind="blade(point, position(point.id) ? 1 : 2, 3, 13)" stroke="black" stroke-width="5" />
        <line v-bind="blade(point, position(point.id) ? 2 : 1, 1, 11)" :stroke="bladeColor(point)"
          stroke-width="5" :class="{ 'blade-flash': pointState(point.id).moving }" />
      </template>
      <circle v-if="snapshot?.switches?.[point.id]?.manual_locked" :cx="point.x" :cy="point.y" r="9" fill="none" stroke="red" />
      <rect v-if="snapshot?.switches?.[point.id]?.sealed" :x="point.x-11" :y="point.y-11" width="22" height="22" fill="none" stroke="red" />
      <g class="device-hit" tabindex="0" role="button" :aria-label="`${point.id} 号道岔`"
        @click="selectSwitch(point)" @keydown.enter="selectSwitch(point)">
        <rect :x="Math.min(point.x,point.geometry.label[0])-14" :y="Math.min(point.y,point.geometry.label[1])-20"
          width="48" :height="Math.abs(point.y-point.geometry.label[1])+38" fill="transparent" />
        <text :x="point.geometry.label[0]" :y="point.geometry.label[1]" :fill="bladeColor(point)"
          :class="{ 'standard-flash': pointState(point.id).moving || lostIndication(point.id) }">{{ point.name }}</text>
        <title>{{ point.id }} 号道岔：{{ switchText(point.id) }}</title>
      </g>
    </g>
    <g aria-label="绝缘节与端部标志">
      <g v-for="joint in joints" :key="joint.offset">
        <line v-if="joint.shape !== 5" v-bind="jointLine(joint)" :stroke="C.gray" stroke-width="1.5" />
        <circle v-if="joint.shape === 3" :cx="joint.center[0]" :cy="joint.center[1]" r="6" fill="none" stroke="red" />
        <polyline v-if="joint.polygon.length && safePoints(joint.polygon)" :points="poly(joint.polygon)" fill="none" :stroke="C.gray" stroke-width="1.5" />
      </g>
    </g>
    <g v-for="signal in station.signals" :key="signal.id" :data-signal="signal.name">
      <g class="device-hit" tabindex="0" role="button" :aria-label="`${signal.name} ${signal.type === 2 ? '调车按钮' : '信号机'}`"
        @click="clickSignal(signal)" @keydown.enter="clickSignal(signal)">
        <line :x1="signal.geometry.fields[4]" :y1="signal.geometry.fields[5]" :x2="signal.geometry.fields[6]"
          :y2="signal.geometry.fields[7]" :stroke="C.idle" />
        <circle v-for="(lamp, i) in lamps(signal)" :key="i" :cx="lamp.x" :cy="lamp.y" r="9"
          :fill="lamp.color" :stroke="C.idle" stroke-width="1.5" :class="{ 'standard-flash': isSelectedSignal(signal) }" />
        <rect v-if="snapshot?.signals?.[signal.name]?.sealed" v-bind="signalBox(signal)" fill="none" stroke="red" stroke-width="2" />
        <rect v-bind="signalBox(signal)" fill="transparent" />
        <text :x="signal.geometry.fields[0]" :y="signal.geometry.fields[1]" :class="{ 'standard-flash': isSelectedSignal(signal) }">{{ signal.name }}</text>
        <text v-if="unlockSeconds(signal.name)" :x="signal.x-12" :y="signal.y-26" fill="red">{{ unlockSeconds(signal.name) }}</text>
        <title>{{ signal.name }}：{{ snapshot?.signals?.[signal.name]?.aspect || '关闭' }}{{ snapshot?.signals?.[signal.name]?.sealed ? '；按钮封锁' : '' }}</title>
      </g>
      <g v-if="signal.type !== 2" class="device-hit" tabindex="0" role="button" :data-button="`${signal.name}LA`"
        :aria-label="`${signal.name}LA 列车按钮`" @click="pressTrain(signal)" @keydown.enter="pressTrain(signal)">
        <rect :x="trainPoint(signal).x-7" :y="trainPoint(signal).y-7" width="14" height="14"
          :fill="C.darkGreen" :stroke="C.gray" stroke-width="2" :class="{ 'standard-flash': selected.includes(`${signal.name}LA`) }" />
        <rect :x="trainPoint(signal).x-12" :y="trainPoint(signal).y-12" width="24" height="24" fill="transparent" />
        <title>{{ signal.name }}LA 列车按钮</title>
      </g>
    </g>
    <g v-for="button in auxiliaryButtons" :key="button.name" class="device-hit" role="button" tabindex="0" :aria-label="button.name"
      @click="emit('press', button.name)" @keydown.enter="emit('press', button.name)">
      <rect :x="button.x-35" :y="button.y-34" width="70" height="48" fill="transparent" />
      <rect :x="button.x-7" :y="button.y-7" width="14" height="14" :fill="C.gray" :stroke="C.silver" />
      <text :x="button.x" :y="button.y-17" text-anchor="middle">{{ button.name }}</text>
    </g>
    <text x="10" y="280" class="direction">东郊方面</text>
    <text x="25" y="320" class="vertical direction">北京方面</text>
    <text x="1400" y="335" class="vertical direction">天津方面</text>
    <text x="1350" y="181" class="direction">牵出线</text>
    <g v-for="block in blockPanels" :key="block.name" :transform="`translate(${block.x},${block.y})`" class="block-panel">
      <rect :width="block.width" height="128" fill="none" :stroke="C.silver" />
      <text x="10" y="22">{{ block.name }}</text>
      <path d="M12 39h27v-5l12 9-12 9v-5H12Z" fill="none" :stroke="blockColor(block.name, 'departure')" />
      <path :d="`M${block.width-14} 39h-27v-5l-12 9 12 9v-5h27Z`" fill="none" :stroke="blockColor(block.name, 'reception')" />
      <text :x="block.width-6" y="22" text-anchor="end" class="block-phase">{{ blockPhase(block.name) }}</text>
      <template v-if="block.name !== 'XD'">
        <circle :cx="block.width/2-25" cy="44" r="6" fill="black" :stroke="C.silver" />
        <circle :cx="block.width/2+45" cy="44" r="6" fill="black" :stroke="C.silver" />
        <text :x="block.width/2-45" y="70">区间</text><text :x="block.width/2+25" y="70">辅助</text>
      </template>
      <g v-for="(name, i) in (block.name === 'XD' ? ['复原','事故','闭塞'] : ['发车辅助','总辅助','接车辅助'])" :key="name" class="block-control" role="button" tabindex="0"
        :aria-label="`${block.name}${name}`" @click="pressBlock(block.name,name)"
        @keydown.enter="pressBlock(block.name,name)">
        <rect :x="block.width*i/3" y="78" :width="block.width/3" height="48" fill="transparent" />
        <rect :x="block.width*(i+0.5)/3-7" y="90" width="14" height="14" :fill="C.gray" :stroke="C.silver" />
        <text :x="block.width*(i+0.5)/3" y="120" text-anchor="middle">{{ name }}</text>
      </g>
    </g>
  </svg>
</template>

<script setup>
import { computed } from 'vue'
import { COLORS as C, lampColors, sectionColor } from './standardDisplay'
const props = defineProps({ station: Object, snapshot: Object, selected: { type: Array, default: () => [] }, targeting: String })
const emit = defineEmits(['press', 'inspect', 'group', 'signal', 'block'])
const tracks = computed(() => props.station.reference_geometry.filter(r => r.type === 3 || r.type === 4))
const joints = computed(() => props.station.reference_geometry.filter(r => r.type === 501))
const auxiliaryButtons = computed(() => props.station.buttons.filter(b => ['BA1','XDDZA','SFDZA','XTA','XFTA','STA','SFTA'].includes(b.name))
  .map(b => ({ ...b, ...({ BA1: { x: 420, y: 245 }, XDDZA: { x: 240, y: 246 }, SFDZA: { x: 1220, y: 326 },
    XTA: { x: 80,y: 420 }, XFTA: { x: 80,y: 500 }, STA: { x: 1370,y: 485 }, SFTA: { x: 1330,y: 290 } })[b.name] })))
const blockPanels = [ { name: 'XD', x: 0, y: 130, width: 126 },
  { name: 'X', x: 0, y: 558, width: 322 }, { name: 'XF', x: 326, y: 558, width: 240 },
  { name: 'SF', x: 794, y: 558, width: 260 }, { name: 'S', x: 1060, y: 558, width: 298 } ]
const poly = points => points.map(p => p.join(',')).join(' ')
const safePoints = points => points.every(([x,y]) => x >= 0 && x <= 1440 && y >= 0 && y <= 740)
const displayedSection = name => { const s=props.snapshot?.sections?.[name]; return s ? {...s, locked:s.display_locked ?? s.locked} : s }
const color = name => sectionColor(displayedSection(name))
const pointState = id => props.snapshot?.switches?.[id] || {}
const position = id => pointState(id).moving ? pointState(id).target_position : pointState(id).position || 0
const lostIndication = id => pointState(id).represented === false && !pointState(id).moving
function blockColor(name,direction) { const b=props.snapshot?.blocks?.[name];return b?.permission && b.direction===direction ? C.green : C.silver }
function blockPhase(name) { return ({ idle:'未闭塞',requested:'请求中',awaiting_peer:'待邻站',permitted:'许可' })[props.snapshot?.blocks?.[name]?.phase] || '' }
function pressBlock(target,label) {
  const type=({'闭塞':'BLOCK_REQUEST','复原':'BLOCK_RESET','事故':'BLOCK_ACCIDENT_RESET','发车辅助':'BLOCK_DEPARTURE_AUX','接车辅助':'BLOCK_RECEPTION_AUX','总辅助':'BLOCK_TOTAL_AUX'})[label]
  emit('block',{ type, fixedTarget:target, label:`${target} ${label}`, sealed:!['BLOCK_REQUEST','BLOCK_RESET'].includes(type) })
}
function branchColor(point,index){const state=displayedSection(point.section);return state?.locked && !state.occupied && index!==0 && index!==(position(point.id)?2:1) ? C.idle : sectionColor(state)}
function jointLine(joint){const [x,y]=joint.center,l=joint.length;return joint.shape===0 ? {x1:x-5,y1:y-5,x2:x+5,y2:y+5} : {x1:x,y1:y-l,x2:x,y2:y+l}}
function sectionText(name) { const s = props.snapshot?.sections?.[name]; return s?.occupied ? '占用' : s?.locked ? '锁闭' : '空闲' }
function inspectSection(name) { emit('inspect', '区段', name, sectionText(name)) }
function switchText(id) { const s=pointState(id); return `${s.moving ? `向${s.target_position ? '反位' : '定位'}转换，等待本端表示` : `${s.position ? '反位' : '定位'}，${s.represented === false ? s.movement_failed ? '转换超时，失表示' : '失表示' : '表示正常'}`}${s.locked ? '，进路锁闭' : ''}${s.manual_locked ? '，单锁' : ''}${s.sealed ? '，封锁' : ''}` }
function selectSwitch(point) { emit('group', point.id); emit('inspect', '道岔', point.id, switchText(point.id)) }
function bladeColor(point) { return lostIndication(point.id) ? C.red : position(point.id) ? C.yellow : C.green }
function blade(point, branch, start, end) {
  const [x,y] = point.geometry.point, [tx,ty] = point.geometry.branches[branch][0] || [x+1,y]
  const l=Math.hypot(tx-x,ty-y)||1, ux=(tx-x)/l, uy=(ty-y)/l
  return { x1:x+ux*start, y1:y+uy*start, x2:x+ux*end, y2:y+uy*end }
}
function lamps(signal) {
  const f=signal.geometry.fields, colors=lampColors(signal.type===2,props.snapshot?.signals?.[signal.name]?.aspect, props.snapshot?.signals?.[signal.name]?.lit !== false)
  return colors.map((color,i) => ({ x:(f[10+i*4]+f[12+i*4])/2, y:(f[11+i*4]+f[13+i*4])/2, color }))
    .filter(p => p.x >= 0 && p.x <= 1440 && p.y >= 0 && p.y <= 740)
}
function signalBox(signal) {
  const lights=lamps(signal),f=signal.geometry.fields
  const left=Math.min(signal.x,f[0],...lights.map(l=>l.x))-13,top=Math.min(signal.y-14,f[1]-18)
  return {x:left,y:top,width:Math.max(signal.x+13,f[0]+signal.name.length*9,...lights.map(l=>l.x+13))-left,height:Math.max(signal.y+14,f[1]+4)-top}
}
function trainPoint(signal) { return { x:signal.x+(signal.geometry.fields[18] ? -18 : 18), y:signal.y } }
function isSelectedSignal(signal) { return props.selected.some(name => name === `${signal.name}DA` || name === `${signal.name}LA`) }
function clickSignal(signal) { if(props.targeting) emit('signal',signal.name); else if(props.station.buttons.some(b=>b.name===`${signal.name}DA`)) emit('press',`${signal.name}DA`); else emit('inspect','信号机',signal.name,props.snapshot?.signals?.[signal.name]?.aspect || '关闭') }
function pressTrain(signal) { if(props.targeting) emit('signal',signal.name); else emit('press',`${signal.name}LA`) }
function unlockSeconds(name) { return props.snapshot?.routes?.find(r=>r.signal===name && r.status==='manual_unlocking')?.manual_remaining_seconds || 0 }
</script>

<style scoped>
.reference-diagram { display:block;width:100%;height:100%;min-width:1180px;min-height:606px;background:#000;font:16px SimHei,'Microsoft YaHei',sans-serif;color:#c0c0c0; }
text { user-select:none;pointer-events:none; }
.station-title { font:30px KaiTi,serif;letter-spacing:5px;fill:#c0c0c0; }
.track { fill:none;stroke-width:3;stroke-linecap:butt;stroke-linejoin:round; }
.section-label { font-size:16px; }
.direction { font:22px KaiTi,serif; }.vertical { writing-mode:vertical-rl;letter-spacing:6px; }
.device-hit,.block-control,[role=button] { cursor:pointer; }
[role=button]:focus-visible { outline:none;filter:drop-shadow(0 0 4px white); }
.block-panel text { font-size:16px; }.block-panel .block-phase { font-size:11px;fill:#ffff00; }.block-control:hover { filter:brightness(1.3); }
.standard-flash { animation:standard-flash 1s steps(1,end) infinite; }@keyframes standard-flash { 50% { opacity:0; } }
.blade-flash { animation:blade-flash 1s steps(1,end) infinite; }@keyframes blade-flash { 50% { stroke:#000; } }
</style>
