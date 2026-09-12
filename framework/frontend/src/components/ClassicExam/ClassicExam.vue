<template>
  <main class="classic-exam-page">
    <header class="exercise-heading">
      <div class="heading-main"><p class="eyebrow">经典例题 <span>/ {{ exam.index }}</span></p><h1>{{ exam.title }}</h1><p class="heading-description">在完整站场上选择按钮、设置道岔、标记敌对信号和检查区段，完成后提交检验。</p></div>
      <div class="heading-actions"><span class="topic-tag">{{ exam.topic }}</span><button class="quiet-button" @click="showOriginal = true">查看原图 ↗</button><router-link to="/student/lobby">返回例题</router-link></div>
    </header>
    <nav class="exam-tabs" aria-label="切换经典例题">
      <router-link v-for="item in exams" :key="item.index" :to="item.route" :class="{ active: item.index === exam.index }"><span>{{ item.index }}</span>{{ item.subtitle }}</router-link>
    </nav>
    <p v-if="exam.conditions" class="condition-note"><strong>题设环境：</strong>23/25、5/7 号道岔均处于定位。环境条件与下方学生答案分开记录；所有设备仍可加入或移出答案。</p>

    <div class="answer-workspace" :inert="submitting">
      <section class="device-inspector" aria-label="设备操作面板" aria-live="polite">
        <div class="inspector-title"><span class="inspector-icon">⌖</span><div><strong>{{ inspectorTitle }}</strong><p>{{ inspectorDescription }}</p></div></div>
        <div class="inspector-actions">
          <template v-if="focus?.kind === 'signals'">
            <button v-for="button in selectedSignal?.buttons || []" :key="button" :data-action="`route-${button}`" :class="['action-button', { selected: answer.route_buttons.includes(button) }]" :aria-pressed="answer.route_buttons.includes(button)" @click="toggle('route_buttons', button)">{{ button.endsWith('LA') ? '列车按钮' : '调车按钮' }} {{ button }} <span v-if="answer.route_buttons.includes(button)">✓</span></button>
            <button :data-action="`hostile-${focus.code}`" :class="['action-button', 'hostile-action', { selected: answer.hostile_signals.includes(focus.code) }]" :aria-pressed="answer.hostile_signals.includes(focus.code)" @click="toggle('hostile_signals', focus.code)">{{ answer.hostile_signals.includes(focus.code) ? '取消敌对标记' : '标记为敌对信号' }} {{ focus.code }}</button>
            <button v-if="selectedSignal?.shuntFunction" :data-action="`hostile-${selectedSignal.shuntFunction}`" :class="['action-button', 'hostile-action', { selected: answer.hostile_signals.includes(selectedSignal.shuntFunction) }]" :aria-pressed="answer.hostile_signals.includes(selectedSignal.shuntFunction)" @click="toggle('hostile_signals', selectedSignal.shuntFunction)">{{ answer.hostile_signals.includes(selectedSignal.shuntFunction) ? '取消调车敌对' : '标记调车敌对' }} {{ selectedSignal.shuntFunction }}</button>
          </template>
          <template v-else-if="focus?.kind === 'switches'">
            <button v-for="position in ['normal', 'reverse']" :key="position" :data-action="`switch-${position}`" :class="['action-button', { selected: answer.switches[focus.code] === position }]" :aria-pressed="answer.switches[focus.code] === position" @click="setSwitch(focus.code, position)">{{ positionName(position) }}</button>
            <button class="quiet-button" data-action="switch-clear" @click="setSwitch(focus.code, null)">清除选择</button>
          </template>
          <template v-else-if="focus?.kind === 'track_sections'">
            <button class="action-button" :class="{ selected: answer.track_sections.includes(focus.code) }" :aria-pressed="answer.track_sections.includes(focus.code)" @click="toggle('track_sections', focus.code)">{{ answer.track_sections.includes(focus.code) ? '取消检查区段' : '选择检查区段' }} {{ focus.code }}</button>
          </template>
          <template v-else-if="focus?.kind === 'route_buttons'">
            <button class="action-button" :class="{ selected: answer.route_buttons.includes(focus.code) }" :aria-pressed="answer.route_buttons.includes(focus.code)" @click="toggle('route_buttons', focus.code)">{{ answer.route_buttons.includes(focus.code) ? '取消按钮' : '选择按钮' }} {{ focus.code }}</button>
          </template>
          <template v-else-if="focus?.kind === 'reference'"><button class="action-button hostile-action" :class="{ selected: answer.hostile_signals.includes(photoSignalCode) }" :aria-pressed="answer.hostile_signals.includes(photoSignalCode)" data-action="hostile-photo-signal" @click="toggle('hostile_signals', photoSignalCode)">{{ answer.hostile_signals.includes(photoSignalCode) ? '取消敌对标记' : '标记为敌对信号' }}</button><button class="quiet-button" @click="showOriginal = true">查看原图对照</button></template>
          <span v-else class="inspector-hint">信号机 / 道岔：点击后在此设置　区段：点击直接选取</span>
        </div>
      </section>
      <p class="mobile-diagram-hint">拖动站场查看全部设备，或展开下方的文字辅助操作。</p>
      <ClassicStationCanvas ref="canvas" :answer="answer" :errors="errorItems" :focus="focus" @inspect="inspect" @toggle-section="toggle('track_sections', $event)" @toggle-hostile="toggle('hostile_signals', $event)" @toggle-button="toggle('route_buttons', $event)" />

      <section class="answer-summary">
        <div class="section-heading"><h2>我的答案</h2><span>与图中操作实时同步</span><button class="quiet-button" data-testid="reset-answer" @click="reset">全部重置</button></div>
        <div class="answer-groups">
          <div v-for="group in summaryGroups" :key="group.kind" class="answer-group" :data-testid="`summary-${group.kind}`">
            <h3>{{ group.label }}<span>{{ group.items.length }}</span></h3>
            <p v-if="!group.items.length" class="empty-answer">尚未选择</p>
            <div v-else class="answer-chips"><button v-for="item in group.items" :key="item.code" class="answer-chip" :title="`点击移除 ${item.label}`" @click="removeItem(group.kind, item.code)">{{ item.label }}<span aria-hidden="true">×</span></button></div>
          </div>
        </div>
        <details class="text-options"><summary>文字辅助操作 <span>与站场图使用同一份答案</span></summary>
          <div class="text-options-body">
            <div class="text-group"><strong>进路按钮</strong><button v-for="code in routeButtons" :key="code" :class="['option-button', { selected: answer.route_buttons.includes(code) }]" :aria-pressed="answer.route_buttons.includes(code)" @click="toggle('route_buttons', code)">{{ code }}</button></div>
            <div class="text-group"><strong>道岔位置</strong><label v-for="sw in switches" :key="sw.id">{{ sw.id }}<select :aria-label="`道岔 ${sw.id} 位置`" :value="answer.switches[sw.id] || ''" @change="setSwitch(sw.id, $event.target.value)"><option value="">未选择</option><option value="normal">定位</option><option value="reverse">反位</option></select></label></div>
            <div class="text-group"><strong>敌对信号</strong><button v-for="code in signalChoices" :key="code" :class="['option-button', { selected: answer.hostile_signals.includes(code) }]" :aria-pressed="answer.hostile_signals.includes(code)" @click="toggle('hostile_signals', code)">{{ code }}</button></div>
            <div class="text-group"><strong>轨道区段</strong><button v-for="sec in sections" :key="sec.name" :class="['option-button', { selected: answer.track_sections.includes(sec.name) }]" :aria-pressed="answer.track_sections.includes(sec.name)" @click="toggle('track_sections', sec.name)">{{ sec.name }}</button></div>
          </div>
        </details>
      </section>
    </div>

    <div class="submit-bar"><div><strong>完成后提交检验</strong><p>按四类答案集合比对；选错、多选或遗漏都会指出。</p></div><button class="submit-button" :disabled="submitting" data-testid="submit-answer" @click="submit">{{ submitting ? '正在检验…' : '提交检验 →' }}</button></div>
    <p v-if="notice" class="notice" role="status">{{ notice }}</p>
    <section v-if="result" ref="resultPanel" class="result-panel" aria-live="polite">
      <div class="result-heading" :class="{ success: result.all_correct }"><span class="result-symbol">{{ result.all_correct ? '✓' : '!' }}</span><div><h2>{{ result.all_correct ? '全部正确' : `发现 ${errorItems.length} 处需要调整` }}</h2><p>{{ result.all_correct ? '按钮、道岔、敌对信号和轨道区段与预设答案一致。' : '点击错误项，可回到站场定位对应设备。修改答案后请重新提交。' }}</p></div></div>
      <div v-if="errorItems.length" class="error-list"><button v-for="(item, i) in errorItems" :key="i" :data-error="`${item.kind}:${item.code}`" @click="locateError(item)"><span class="error-badge">{{ item.type }}</span><span><strong>{{ item.code }}</strong><small>{{ item.message }}</small></span><span class="locate-arrow">定位 ↗</span></button></div>
      <details class="comparison-details"><summary>查看本次提交与预设答案对照</summary><div class="comparison-scroll"><table><thead><tr><th>类别</th><th>本次提交</th><th>预设答案</th></tr></thead><tbody><tr v-for="row in comparisonRows" :key="row.label"><td>{{ row.label }}</td><td>{{ row.student }}</td><td>{{ row.correct }}</td></tr></tbody></table></div></details>
      <div v-if="!result.all_correct" class="ai-area" :aria-busy="aiLoading">
        <button class="action-button" :disabled="aiLoading" data-testid="ai-explain" @click="explain">{{ aiLoading ? '正在分析错误原因…' : aiResult ? '重新尝试 AI 解析' : 'AI 解析错误原因' }}</button>
        <span>围绕本次提交，解释错在哪里、原因和后果。</span>
        <p v-if="aiLoading" class="ai-progress" role="status">正在整理本次错误；遇到临时异常会自动尝试一次，请稍候。</p>
        <div v-if="aiResult" class="ai-explanation" data-testid="ai-explanation">
          <div class="ai-result-header"><strong :class="{ fallback: aiResult.source === 'rules_fallback' }" data-testid="ai-source">{{ aiResult.source === 'ai' ? 'AI 辅助解析' : aiResult.source === 'rules_fallback' ? '规则解析' : '答案核对' }}</strong><p data-testid="ai-status" role="status">{{ aiResult.message }}</p></div>
          <p v-if="aiResult.route_summary" class="ai-route" data-testid="ai-route">{{ aiResult.route_summary }}</p>
          <article v-for="item in aiResult.items" :key="item.id" class="ai-error-card" :data-explanation-id="item.id">
            <h3>{{ item.title }}</h3>
            <dl><dt>错在哪里</dt><dd>{{ item.diagnosis }}</dd><dt>为什么</dt><dd>{{ item.reason }}</dd><dt>如何纠正</dt><dd>{{ item.correction }}</dd><dt>不纠正的影响</dt><dd>{{ item.consequence }}</dd></dl>
          </article>
          <p v-if="!aiResult.items.length">{{ aiExplanation }}</p>
        </div>
      </div>
    </section>
    <el-dialog v-model="showOriginal" title="原始站场图 · 铅笔圈定范围" width="92%" top="4vh" destroy-on-close>
      <p class="original-caption">四道经典例题使用同一圈定范围。站场图保留连接关系，编号与区段依据项目既有资料整理。</p>
      <svg viewBox="0 0 1706 1279" class="original-photo" role="img" aria-label="旋正显示的原始站场照片"><image :href="originalUrl" width="1279" height="1706" transform="translate(0 1279) rotate(-90)" /></svg>
    </el-dialog>
  </main>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import ClassicStationCanvas from './ClassicStationCanvas.vue'
import { exams, signals, switches, sections, signalChoices, routeButtons, emptyAnswer, copyAnswer, photoSignalCode } from '@/domain/classicStation'
import { submitInterlockingExam, requestAiExplanation } from '@/api/interlockingExam'
import originalUrl from '../../../../../pictures/原始图.jpg?url'

const props = defineProps({ routeType: { type: String, required: true } })
const exam = computed(() => exams[props.routeType])
const answer = ref(emptyAnswer(props.routeType)), focus = ref(null), canvas = ref(null), resultPanel = ref(null)
const result = ref(null), submitted = ref(null), submitting = ref(false), aiLoading = ref(false), aiExplanation = ref(''), notice = ref(''), showOriginal = ref(false)
const aiResult = ref(null)
let revision = 0, aiRequest = 0
let aiController = null
function cancelExplanation() { aiRequest++; aiController?.abort(); aiController = null; aiLoading.value = false }
onBeforeUnmount(cancelExplanation)
const categories = { route_buttons: '进路按钮', switches: '道岔位置', hostile_signals: '敌对信号', track_sections: '轨道区段' }
const positionName = p => p === 'normal' ? '定位' : p === 'reverse' ? '反位' : '未选择'
const selectedSignal = computed(() => signals.find(s => s.name === focus.value?.code))
const inspectorTitle = computed(() => !focus.value ? '点击图中设备，开始作答' : `${focus.value.code}${focus.value.kind === 'switches' ? ' 号道岔' : focus.value.kind === 'track_sections' ? ' 轨道区段' : focus.value.kind === 'signals' ? ' 信号操作' : ''}`)
const inspectorDescription = computed(() => {
  if (!focus.value) return '完整站场中的设备均可交互，由你决定答案。'
  if (focus.value.kind === 'switches') {
    const given = exam.value.conditions?.[focus.value.code]
    return `${focus.value.code.includes('/') ? '双动道岔两端同步设置。' : '单动道岔。'}当前答案：${positionName(answer.value.switches[focus.value.code])}${given ? `；题设环境：${positionName(given)}` : ''}`
  }
  if (focus.value.kind === 'signals') return selectedSignal.value ? `${selectedSignal.value.type}信号机 · ${selectedSignal.value.track} 股道 · 进路按钮与敌对标记分别选择` : '出站信号机的调车功能；可单独列入敌对信号答案。'
  if (focus.value.kind === 'track_sections') return '选择表示列入需要检查的区段，颜色表示你的作答。'
  if (focus.value.kind === 'reference') return '原图 Y_XD 预告信号，可选择是否列入敌对信号。'
  return '北京方面的列车发车终端按钮。'
})
function inspect(kind, code) { focus.value = { kind, code } }
function toggle(kind, code) { const list = answer.value[kind]; const index = list.indexOf(code); if (index >= 0) list.splice(index, 1); else list.push(code) }
function setSwitch(code, position) { if (position) answer.value.switches[code] = position; else delete answer.value.switches[code] }
function removeItem(kind, code) { if (kind === 'switches') setSwitch(code, null); else toggle(kind, code) }
function reset() { answer.value = emptyAnswer(props.routeType); focus.value = null; canvas.value?.fit(); notice.value = '' }
watch(answer, () => { revision++; cancelExplanation(); result.value = null; submitted.value = null; aiExplanation.value = ''; aiResult.value = null; notice.value = '' }, { deep: true, flush: 'sync' })
watch(() => props.routeType, reset)
const summaryGroups = computed(() => Object.entries(categories).map(([kind, label]) => ({ kind, label, items: kind === 'switches' ? Object.entries(answer.value.switches).map(([code, p]) => ({ code, label: `${code} · ${positionName(p)}` })) : answer.value[kind].map(code => ({ code, label: code })) })))
const errorItems = computed(() => {
  const errors = result.value?.details?.errors
  if (!errors) return []
  return Object.entries(categories).flatMap(([kind, label]) => {
    const group = errors[kind] || {}
    return [
      ...(group.missing || []).map(code => ({ kind, code, type: '漏选', message: `${label}中缺少此项${kind === 'switches' ? `，应为${positionName(group.correct[code])}` : ''}` })),
      ...(group.extra || []).map(code => ({ kind, code, type: '多选', message: `${label}中多选了此项` })),
      ...(group.wrong_position || []).map(e => ({ kind, code: e.switch, type: '错位', message: `当前${positionName(e.student)}，应为${positionName(e.expected)}` })),
    ]
  })
})
function formatValue(kind, value) { if (kind === 'switches') return Object.entries(value || {}).map(([c, p]) => `${c}（${positionName(p)}）`).join('、') || '未选择'; return value?.join('、') || '未选择' }
const comparisonRows = computed(() => !submitted.value || !result.value?.details?.correct_answer ? [] : Object.entries(categories).map(([kind, label]) => ({ label, student: formatValue(kind, submitted.value[kind]), correct: formatValue(kind, result.value.details.correct_answer[kind]) })))
function locateError(item) {
  const kind = item.code === photoSignalCode ? 'reference' : item.kind === 'hostile_signals' ? 'signals' : item.kind === 'route_buttons' && item.code !== 'SLZA' ? 'signals' : item.kind
  const sig = signals.find(s => s.buttons.includes(item.code))
  inspect(kind, kind === 'signals' && sig ? sig.name : item.code)
  canvas.value?.locate(item.kind, item.code)
  document.querySelector('.station-board')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}
async function submit() {
  if (submitting.value) return
  const snapshot = copyAnswer(answer.value), requestRevision = revision
  submitting.value = true; result.value = null; cancelExplanation(); aiExplanation.value = ''; aiResult.value = null; notice.value = ''
  try {
    const response = await submitInterlockingExam(snapshot)
    if (requestRevision !== revision) return
    submitted.value = snapshot; result.value = response
    await nextTick(); resultPanel.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  } catch (error) { if (requestRevision === revision) notice.value = `提交失败：${error.response?.data?.detail || error.message}。当前答案已保留，可以重试。` }
  finally { submitting.value = false }
}
async function explain() {
  if (!submitted.value || !result.value || aiLoading.value) return
  const requestId = ++aiRequest, snapshot = copyAnswer(submitted.value)
  const controller = new AbortController()
  aiController = controller
  aiLoading.value = true; notice.value = ''
  try {
    const response = await requestAiExplanation(snapshot, controller.signal)
    if (requestId !== aiRequest) return
    const validItems = Array.isArray(response?.items) && response.items.every(item => item && ['id', 'title', 'diagnosis', 'reason', 'correction', 'consequence'].every(key => typeof item[key] === 'string' && item[key].trim()))
    const expectedIds = Object.entries(result.value.details.errors).flatMap(([category, errors]) => ['missing', 'extra', 'wrong_position'].flatMap(kind => (errors[kind] || []).map(item => `${category}:${kind}:${kind === 'wrong_position' ? item.switch : item}`)))
    const receivedIds = validItems ? response.items.map(item => item.id) : []
    const completeCoverage = receivedIds.length === expectedIds.length && new Set(receivedIds).size === receivedIds.length && expectedIds.every(id => receivedIds.includes(id))
    if (typeof response?.ai_explanation !== 'string' || !response.ai_explanation.trim() || !['ai', 'rules_fallback'].includes(response.source) || typeof response.message !== 'string' || !response.message.trim() || typeof response.route_summary !== 'string' || !validItems || !completeCoverage) {
      const error = new Error('未收到完整有效的解析，请重新尝试。')
      error.localMessage = error.message
      throw error
    }
    aiExplanation.value = response.ai_explanation
    aiResult.value = response
  } catch (error) {
    if (requestId === aiRequest && error.code !== 'ERR_CANCELED') {
      const detail = error.response?.data?.detail
      const message = error.localMessage || (typeof detail === 'string' ? detail : error.code === 'ECONNABORTED' ? '解析等待超时，请稍后重试。' : error.response ? '解析服务未能完成本次请求，请稍后重试。' : '暂时无法连接解析服务，请检查连接后重试。')
      notice.value = `${message} 本次判分结果和答案已保留。`
    }
  } finally { if (requestId === aiRequest) { aiLoading.value = false; aiController = null } }
}
</script>

<style scoped>
.classic-exam-page { max-width: 1600px; margin: 0 auto; padding: 8px 4px 40px; color: #22384b; }
.exercise-heading { display: flex; justify-content: space-between; align-items: flex-start; gap: 20px; padding: 8px 0 20px; }
.eyebrow { font-size: var(--ui-text-base); font-weight: 700; letter-spacing: 2px; color: #36768c; margin: 0 0 12px; }.eyebrow span { color: #586f82; }
h1 { font-size: clamp(var(--ui-text-heading), 1.8vw, 31px); margin: 0 0 12px; font-weight: 700; line-height: 1.5; }
.heading-description { color: #718190; font-size: var(--ui-text-base); line-height: 1.8; margin: 0; }
.heading-actions { display: flex; align-items: center; flex-wrap: wrap; justify-content: flex-end; gap: 12px; min-width: 140px; padding-top: 7px; }
.topic-tag { border: 1px solid #bad3dd; color: #326b80; background: #eaf4f7; border-radius: 20px; padding: 5px 12px; font-size: var(--ui-text-base); white-space: nowrap; }
.heading-actions a { color: #657c90; text-decoration: none; font-size: var(--ui-text-base); }
.quiet-button { border: 0; background: none; color: #567c94; cursor: pointer; padding: 6px; font: inherit; font-size: var(--ui-text-base); }
.exam-tabs { display: flex; gap: 4px; background: #e7edf2; border-radius: 10px; padding: 5px; margin-bottom: 16px; }
.exam-tabs a { flex: 1; padding: 12px 8px; border-radius: 7px; color: #607588; text-align: center; text-decoration: none; font-size: var(--ui-text-base); line-height: 1.5; }.exam-tabs a span { margin-right: 8px; opacity: .7; }.exam-tabs a.active { background: #fff; color: #216484; font-weight: 700; box-shadow: 0 2px 7px #18334d0b; }
.condition-note { font-size: var(--ui-text-base); padding: 12px 16px; background: #fff8e9; color: #816124; border: 1px solid #f0deb3; border-radius: 8px; line-height: 1.8; }
.device-inspector { position: sticky; top: 0; z-index: 5; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; background: #fff; border: 1px solid #dbe5ec; border-radius: 10px; padding: 14px 18px; margin-bottom: 12px; box-shadow: 0 4px 18px #294b7210; min-height: 84px; }
.inspector-title { display: flex; gap: 12px; align-items: center; }.inspector-title strong { font-size: var(--ui-text-md); }.inspector-title p { margin: 6px 0 0; color: #586f82; font-size: var(--ui-text-base); line-height: 1.5; }.inspector-icon { font-size: 30px; color: #586f82; }.inspector-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }.inspector-hint { color: #586f82; font-size: var(--ui-text-base); }
.action-button { background: #f4f8fb; border: 1px solid #c8d9e5; color: #315e7b; border-radius: 7px; padding: 10px 13px; font: inherit; font-size: var(--ui-text-base); cursor: pointer; }.action-button.selected { background: #e3f2fb; border-color: #4c9ac6; color: #1c6896; }.hostile-action.selected { background: #efe9fb; border-color: #a389c9; color: #704d9a; }
.answer-summary { margin-top: 18px; background: white; border: 1px solid #dfe7ee; border-radius: 12px; overflow: hidden; }.section-heading { display: flex; align-items: center; gap: 12px; padding: 17px 20px; }.section-heading h2 { font-size: var(--ui-text-md); margin: 0; }.section-heading > span { font-size: var(--ui-text-base); color: #586f82; }.section-heading > button { margin-left: auto; }
.answer-groups { display: grid; grid-template-columns: repeat(4, 1fr); padding: 0 20px 18px; gap: 20px; }.answer-group h3 { display: flex; align-items: center; gap: 8px; font-size: var(--ui-text-base); color: #718596; margin: 0 0 12px; font-weight: 500; }.answer-group h3 span { background: #ecf2f6; padding: 2px 6px; border-radius: 4px; font-size: var(--ui-text-sm); }.empty-answer { font-size: var(--ui-text-base); color: #586f82; }.answer-chips { display: flex; flex-wrap: wrap; gap: 5px; }.answer-chip { background: #edf5fa; border: 1px solid #d8e7f0; border-radius: 5px; color: #426d89; padding: 6px 8px; cursor: pointer; font-size: var(--ui-text-meta); }.answer-chip span { margin-left: 8px; color: #586f82; }
.text-options { border-top: 1px solid #e8eef3; }.text-options summary { padding: 14px 20px; font-size: var(--ui-text-base); cursor: pointer; color: #5d7d92; }.text-options summary span { color: #586f82; margin-left: 15px; }.text-options-body { padding: 0 20px 16px; }.text-group { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-top: 16px; }.text-group strong { flex-basis: 100%; font-size: var(--ui-text-base); }.text-group label { font-size: var(--ui-text-base); background: #f5f8fa; padding: 6px; border-radius: 4px; }.text-group select { margin-left: 8px; padding: 4px; border: 1px solid #cfdae2; border-radius: 4px; color: #3d6078; }.option-button { background: #f5f8fa; border: 1px solid #d8e2e9; color: #60778b; border-radius: 5px; padding: 6px 9px; cursor: pointer; }.option-button.selected { background: #dcedf8; color: #235a81; border-color: #88b6d3; }
.submit-bar { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin: 20px 0; }.submit-bar strong { font-size: var(--ui-text-body); }.submit-bar p { color: #586f82; font-size: var(--ui-text-base); margin: 7px 0 0; }.submit-button { background: #216c8c; color: #fff; border: 0; border-radius: 8px; padding: 14px 30px; font: inherit; font-size: var(--ui-text-body); font-weight: 700; cursor: pointer; box-shadow: 0 4px 10px #216c8c22; }button:disabled { opacity: .6; cursor: wait; }button:focus-visible, a:focus-visible, summary:focus-visible, select:focus-visible { outline: 3px solid #54a6da; outline-offset: 3px; }
.notice { color: #ae5a2c; background: #fff6e9; padding: 12px; border-radius: 7px; font-size: var(--ui-text-base); }
.result-panel { border: 1px solid #e0e7ed; border-radius: 12px; background: #fff; padding: 22px; scroll-margin-top: 105px; }.result-heading { display: flex; align-items: center; gap: 15px; color: #99623f; }.result-symbol { display: grid; place-items: center; width: 38px; height: 38px; background: #fff0e5; border-radius: 50%; font-size: var(--ui-text-heading); font-weight: 700; }.result-heading h2 { font-size: var(--ui-text-lead); margin: 0; }.result-heading p { font-size: var(--ui-text-base); color: #586f82; margin: 8px 0 0; }.result-heading.success { color: #288778; }.success .result-symbol { background: #e8f6f0; }
.error-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin-top: 20px; }.error-list button { display: flex; align-items: center; gap: 12px; text-align: left; background: #fbfcfd; border: 1px solid #e4e9ee; border-radius: 8px; padding: 12px; cursor: pointer; color: #4a6378; }.error-badge { color: #b97951; font-size: var(--ui-text-meta); padding: 4px 6px; background: #fff0e6; border-radius: 4px; white-space: nowrap; }.error-list strong { font-size: var(--ui-text-base); }.error-list small { display: block; color: #586f82; margin-top: 5px; line-height: 1.5; }.locate-arrow { margin-left: auto; font-size: var(--ui-text-meta); color: #586f82; white-space: nowrap; }
.comparison-details { margin-top: 20px; }.comparison-details summary { font-size: var(--ui-text-base); color: #628098; cursor: pointer; padding: 10px 0; }.comparison-scroll { overflow-x: auto; }table { border-collapse: collapse; width: 100%; font-size: var(--ui-text-base); table-layout: fixed; }th, td { padding: 12px; border: 1px solid #e1e9f0; line-height: 1.8; overflow-wrap: anywhere; text-align: left; }th { background: #f3f7fa; }th:first-child { width: 95px; }
.ai-area { border-top: 1px solid #e9eef2; margin-top: 15px; padding-top: 18px; }.ai-area > span { font-size: var(--ui-text-base); color: #586f82; margin-left: 10px; }.ai-explanation { white-space: pre-wrap; overflow-wrap: anywhere; background: #f4f8fb; border-radius: 8px; padding: 18px; margin-top: 15px; font-size: var(--ui-text-body); line-height: 1.9; }
.original-photo { width: 100%; max-height: 75vh; background: #f0e8dc; }.original-caption { font-size: var(--ui-text-base); color: #768797; margin-top: 0; }
.ai-explanation { white-space: normal; }
.ai-progress { font-size: var(--ui-text-base); color: #577e96; }
.ai-result-header { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }
.ai-result-header strong { font-size: var(--ui-text-base); color: #216c8c; white-space: nowrap; }
.ai-result-header strong.fallback { color: #93612e; }
.ai-result-header p { flex: 1; margin: 0; font-size: var(--ui-text-base); color: #687f90; }
.ai-route { background: #e8f1f6; border-radius: 6px; padding: 12px; }
.ai-error-card { background: white; border: 1px solid #dce7ee; border-radius: 8px; margin-top: 14px; padding: 14px 18px; }
.ai-error-card h3 { margin: 0 0 12px; font-size: var(--ui-text-body); color: #2c607c; }
.ai-error-card dl { display: grid; grid-template-columns: 100px minmax(0, 1fr); gap: 9px 12px; margin: 0; }
.ai-error-card dt { color: #728696; font-size: var(--ui-text-base); }
.ai-error-card dd { margin: 0; overflow-wrap: anywhere; }
@media (max-width: 750px) { .ai-error-card dl { grid-template-columns: 1fr; gap: 3px; }.ai-error-card dd { margin-bottom: 9px; } }
@media (max-width: 1250px) { .answer-groups { grid-template-columns: repeat(2, 1fr); }.heading-actions { flex-direction: column; }.exam-tabs a { font-size: var(--ui-text-meta); }.error-list { grid-template-columns: 1fr; } }
@media (prefers-reduced-motion: reduce) { * { scroll-behavior: auto !important; } }
</style>
