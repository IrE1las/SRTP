<template>
  <section class="record-console" v-loading="loading" :aria-busy="loading || busy">
    <div v-if="error" class="console-error" role="alert"><span>{{ error }}</span><el-button :loading="busy" @click="recover">同步并重试</el-button></div>
    <div class="console-actions"><p>先选功能，再选目标；办理进路可直接点击始、终端按钮。</p><div><label for="station-scale">站场显示</label><select id="station-scale" v-model="viewScale" name="station-scale"><option value="fit">适应窗口</option><option value="100">原始大小</option><option value="125">放大 125%</option></select><el-button :disabled="busy" @click="refresh">同步状态</el-button><el-button v-if="!examMode" @click="fullscreen">全屏站场</el-button></div></div>
    <p v-if="viewNotice" class="view-notice" role="status">{{ viewNotice }}</p>
    <div class="station-console" ref="root">
      <button class="fullscreen-exit" type="button" @click="exitFullscreen">退出全屏（Esc）</button>
      <div class="diagram" :class="{ unavailable: blocked || busy, native: viewScale !== 'fit' }" :style="{ '--diagram-width': viewScale === '125' ? '1800px' : '1440px', '--diagram-height': viewScale === '125' ? '925px' : '740px' }" :inert="blocked || busy || undefined" :aria-disabled="blocked || busy">
        <ReferenceStationDiagram v-if="station && result" :station="station" :snapshot="result.snapshot" :selected="result.snapshot.selected_buttons" :targeting="result.pending?.target" @press="press" @group="group" @signal="signal" @inspect="inspect" @block="block" />
      </div>
      <div class="functions" role="group" aria-label="联锁功能按钮"><button v-for="item in COMMANDS" :key="item.type" type="button" :disabled="blocked" :class="{ selected: result?.pending?.type === item.type }" :aria-pressed="result?.pending?.type === item.type" @click="choose(item)">{{ item.label }}<span v-if="item.sealed" class="sealed-mark" title="需要教学操作口令" aria-label="需要口令"> ·</span></button></div>
      <p class="hint" aria-live="polite"><span class="hint-label">{{ result?.status === 'active' ? '当前操作' : '只读记录' }}</span>{{ result?.pending ? `${label(result.pending.type)}：请选择${targetLabel(result.pending.target)}` : result?.snapshot?.last_message || '等待加载…' }}<span v-if="result?.snapshot?.selection_remaining_seconds"> · 始端选择剩余 {{ result.snapshot.selection_remaining_seconds }} 秒</span></p>
    </div>
    <el-dialog v-model="showPin" title="输入教学操作口令" width="min(420px, 92vw)" :close-on-click-modal="false" :before-close="closePin" @opened="focusPin">
      <form id="operation-pin-form" class="pin-form" @submit.prevent="confirmPin"><p>本次功能操作需要口令，确认后选择目标设备。</p><label for="operation-pin">教学操作口令</label><input id="operation-pin" ref="pinInput" v-model="pin" name="operation-pin" type="password" autocomplete="off" maxlength="32" required></form>
      <template #footer><el-button @click="cancelPin">取消选择</el-button><el-button type="primary" native-type="submit" form="operation-pin-form">确认口令</el-button></template>
    </el-dialog>
  </section>
</template>
<script setup>
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import ReferenceStationDiagram from './ReferenceStationDiagram.vue'
import { COMMANDS } from './standardDisplay'
import { getOperationStation, getOperationSession, postOperationEvent } from '@/api/operations'
import { eventEnvelope, persistableEvent } from '@/domain/operationEvents'
const props = defineProps({ sessionId: { type: String, required: true }, readOnly: { type: Boolean, default: false }, api: { type: Object, default: null }, examMode: { type: Boolean, default: false }, pausePending: { type: Boolean, default: false } })
const emit = defineEmits(['update'])
const station = ref(null), result = ref(null), loading = ref(true), busy = ref(false), error = ref(''), root = ref(null)
const showPin = ref(false), pin = ref(''), pinInput = ref(null), viewScale = ref('fit'), viewNotice = ref('')
let confirmedPin = '', queue = Promise.resolve(), timer, disposed = false, outstanding = null
const key = 'srtp-operation-pending-' + props.sessionId
const sealed = new Set(COMMANDS.filter(c => c.sealed).map(c => c.type).concat(['BLOCK_ACCIDENT_RESET','BLOCK_TOTAL_AUX','BLOCK_DEPARTURE_AUX','BLOCK_RECEPTION_AUX']))
const blocked = computed(() => props.readOnly || result.value?.read_only || loading.value || !!error.value || showPin.value || result.value?.status !== 'active')
function label(type) { return COMMANDS.find(c => c.type === type)?.label || type }
function targetLabel(type) { return ({ switch:'道岔', signal:'信号机', route:'原进路始端信号', section:'区段', block:'区间按钮' })[type] || type }
function accept(data) {
  if (result.value && (data.revision < result.value.revision || result.value.status !== 'active' && data.status === 'active')) return
  result.value = data; emit('update', data)
}
function enqueue(action, values = {}) {
  if (blocked.value) return Promise.resolve()
  queue = queue.then(async () => {
    if (disposed || props.pausePending || error.value || result.value?.status !== 'active') return
    busy.value = true
    const event = eventEnvelope(action, result.value.revision + 1, values)
    outstanding = persistableEvent(event)
    sessionStorage.setItem(key, JSON.stringify(outstanding))
    try {
      accept(await (props.api?.event || postOperationEvent)(props.sessionId, event))
      outstanding = null; sessionStorage.removeItem(key)
    } catch (e) {
      error.value = e.response?.data?.detail || '操作尚未确认，已暂停；请同步并重试。'
    } finally { busy.value = false }
  })
  return queue
}
async function choose(item) {
  if (item.unavailable) return
  confirmedPin = ''
  await enqueue('function', { button_id: item.type })
  if (!error.value && sealed.has(item.type)) { showPin.value = true; pin.value = '' }
}
function confirmPin() { if (!pin.value) return; confirmedPin = pin.value; pin.value = ''; showPin.value = false; if (deferredBlock) { const id = deferredBlock; deferredBlock = null; target('block', id) } }
async function cancelPin() { showPin.value = false; pin.value = ''; confirmedPin = ''; deferredBlock = null; await enqueue('cancel_selection') }
async function target(kind, id) {
  if (result.value?.pending && sealed.has(result.value.pending.type) && !confirmedPin) { showPin.value = true; return }
  await enqueue('target', { target_id: id, target_kind: kind, pin: confirmedPin || null })
  if (!result.value?.pending) confirmedPin = ''
}
function press(button) { return result.value?.pending ? target('signal', station.value.buttons.find(b => b.name === button)?.signal) : enqueue('button', { button_id: button }) }
function group(id) { if (result.value?.pending) target('switch', id) }
function signal(id) { if (result.value?.pending) target('signal', id) }
function inspect(type, id) { if (type === '区段' && result.value?.pending) target('section', id) }
async function block(item) { await choose(item); if (!sealed.has(item.type) && !error.value) await target('block', item.fixedTarget); else deferredBlock = item.fixedTarget }
let deferredBlock = null
// A fixed-target block button still has a distinct function selection and target event.
const hasUnconfirmed = computed(() => busy.value || !!outstanding)
function focusPin() { pinInput.value?.focus() }
function closePin(done) { cancelPin().finally(done) }
async function exitFullscreen() { await document.exitFullscreen?.() }
defineExpose({ hasUnconfirmed, sync: accept,
  recover: async () => { await queue; await recover(); if (outstanding || error.value) throw new Error(error.value || '操作尚未确认'); return result.value },
  flush: async () => { await queue; if (outstanding || error.value) throw new Error('请先同步未确认的操作'); return result.value } })
async function refresh() {
  if (busy.value || disposed || outstanding) return
  try { accept(await (props.api?.console || getOperationSession)(props.sessionId)); error.value = '' }
  catch { error.value = '连接中断，业务操作已暂停。' }
}
async function recover() {
  busy.value = true
  try {
    if (!station.value) station.value = await (props.api?.station || getOperationStation)()
    accept(await (props.api?.console || getOperationSession)(props.sessionId))
    if (outstanding) {
      // PIN is intentionally absent after reload. Ask again instead of persisting it.
      if (result.value.pending && sealed.has(result.value.pending.type) && !confirmedPin && outstanding.sequence > result.value.revision) {
        error.value = '请输入教学口令后再次点击“同步并重试”。'; showPin.value = true; return
      }
      accept(await (props.api?.event || postOperationEvent)(props.sessionId, { ...outstanding, pin: confirmedPin || null }))
      outstanding = null; sessionStorage.removeItem(key)
    }
    error.value = ''
  } catch (e) { error.value = e.response?.data?.detail || '同步失败，请保留页面并重试。' }
  finally { busy.value = false }
}
async function fullscreen() { try { await root.value?.requestFullscreen() } catch { viewNotice.value = '未能进入全屏，可以继续在当前窗口操作。' } }
onMounted(async () => {
  try {
    station.value = await (props.api?.station || getOperationStation)()
    const initial = await (props.api?.console || getOperationSession)(props.sessionId)
    if (disposed) return
    accept(initial)
    const stored = sessionStorage.getItem(key)
    if (stored) { outstanding = JSON.parse(stored); error.value = '存在尚未确认的点击，请同步并重试。' }
    if (result.value.pending && sealed.has(result.value.pending.type)) showPin.value = true
    timer = setInterval(refresh, 1000)
  } catch { error.value = '操作台加载失败，请同步重试。' }
  finally { loading.value = false }
})
onBeforeUnmount(() => { disposed = true; clearInterval(timer); confirmedPin = ''; pin.value = '' })
</script>
<style scoped>
.record-console{position:relative;flex:1;display:flex;flex-direction:column;min-height:0}.console-actions{display:flex;justify-content:space-between;align-items:center;gap:12px;margin:0 0 10px;color:#586f82;flex-wrap:wrap}.console-actions p{font-size:13px;margin:0}.console-actions>div{display:flex;gap:10px;align-items:center;font-size:13px;flex-wrap:wrap}.console-actions label{font-size:13px}.console-actions select{min-height:36px;min-width:115px;background:white;color:#19334d;border:1px solid #c8d6e3;border-radius:5px;padding:5px 10px;font-size:13px}.console-actions .el-button{min-height:36px;font-size:13px;padding:6px 10px}.station-console{position:relative;display:flex;flex-direction:column;flex:1;min-height:0;background:#000;border:1px solid #b6c7d8;border-radius:6px;overflow:hidden}.station-console:fullscreen{width:100vw;height:100dvh;border:0;border-radius:0}.diagram{flex:1;min-height:260px;overflow:auto;overscroll-behavior:contain;background:#000}.diagram :deep(.reference-diagram){min-width:0;min-height:0;width:100%;height:100%}.diagram.native :deep(.reference-diagram){width:var(--diagram-width);height:var(--diagram-height);max-width:none}.diagram.unavailable{pointer-events:none;opacity:.78}.functions{display:flex;flex-wrap:wrap;gap:6px;padding:10px;background:#e6ebf1;border-top:1px solid #b6c7d8}.functions button{font:14px 'Microsoft YaHei',sans-serif;line-height:1.4;min-height:40px;padding:8px 11px;border:1px solid #aebecf;border-radius:4px;color:#19334d;background:#fff;cursor:pointer;box-shadow:0 1px 0 #aebecf}.functions button:hover:enabled{border-color:#0075b7;background:#edf6fc}.functions button.selected{background:#fff2a1;border-color:#b98b15;color:#302900;box-shadow:inset 0 0 0 1px #b98b15}.functions button:disabled{opacity:.55;cursor:default}.sealed-mark{font-weight:bold;color:#8c6239}.hint{font-size:14px;padding:10px 14px;background:#f8fafc;color:#19334d;margin:0;min-height:44px;border-top:1px solid #d3dee8;line-height:1.7;overflow-wrap:anywhere}.hint-label{color:#586f82;margin-right:16px;font-size:13px}.console-error{background:#fff1e7;color:#9b4423;padding:10px 14px;display:flex;justify-content:space-between;align-items:center;gap:18px;font-size:14px;margin-bottom:10px}.console-error .el-button{flex-shrink:0}.view-notice{font-size:13px;color:#586f82;margin:0 0 8px}.pin-form{display:grid;gap:12px}.pin-form p{margin:0 0 10px;color:#586f82;font-size:14px}.pin-form label{font-weight:600}.pin-form input{padding:10px 12px;border:1px solid #b6c9d8;border-radius:6px;font:inherit;width:100%}
.fullscreen-exit{display:none}.station-console:fullscreen .fullscreen-exit{display:block;position:absolute;top:12px;right:14px;z-index:2;background:#eef5fc;color:#19334d;border:1px solid #b6c9d8;border-radius:5px;padding:8px 14px;font-size:14px}
@media(max-width:650px){.record-console{min-height:610px}.console-actions>p{display:none}.console-actions>div{gap:8px}.functions{padding:8px;gap:5px}.functions button{font-size:13px;padding:7px 9px}.hint{font-size:13px}.diagram{min-height:300px}}
@media(prefers-reduced-motion:reduce){.diagram :deep(.standard-flash),.diagram :deep(.blade-flash){animation:none}}
</style>
