<template>
  <article class="bank-question">
    <div class="question-number" aria-hidden="true">{{ String(ordinal).padStart(2, '0') }}</div>
    <div class="question-content">
      <div class="question-meta">
        <div class="question-tags">
          <span class="kind-tag">{{ kindLabel(item.kind) }}</span>
          <span class="status-tag" :class="{ pending: !isAnswered(item.answer_status) }">{{ answerStatusLabel(item.answer_status) }}</span>
          <span v-if="item.scope" class="scope-label" :class="{ 'station-scope': ['station', 'station_specific'].includes(item.scope) }">{{ scopeLabel(item.scope) }}</span>
          <span v-if="item.has_image" class="image-label">原资料含图</span>
        </div>
        <span class="question-id">题号 {{ item.id }}</span>
      </div>
      <p class="question-stem">{{ item.stem }}</p>
      <ul v-if="options.length" class="question-options" aria-label="题目选项">
        <li v-for="(option, index) in options" :key="index"><span class="option-key">{{ option.key }}</span><span>{{ option.text }}</span></li>
      </ul>
      <div class="question-source">
        <span class="source-label">来源</span>
        <div>
          <p>{{ item.source_reference || '来源信息待补充' }} <a v-if="safeSourceUrl(item.source_url)" :href="safeSourceUrl(item.source_url)" target="_blank" rel="noopener noreferrer">查看来源 ↗</a></p>
          <p v-if="item.source_kind || item.batch" class="source-details"><span v-if="item.source_kind">{{ sourceKindLabel(item.source_kind) }}</span><span v-if="item.batch">收录批次：{{ item.batch }}</span></p>
        </div>
      </div>
      <template v-if="canViewReference">
        <button class="reference-toggle" type="button" :aria-expanded="Boolean(reference?.open)" :aria-controls="referenceId" @click="$emit('toggle-reference', item.id)">
          <span>{{ reference?.open ? '收起参考答案与依据' : '参考答案与依据' }}</span><span aria-hidden="true">{{ reference?.open ? '−' : '+' }}</span>
        </button>
        <section v-if="reference?.open" :id="referenceId" class="reference-panel" aria-label="参考答案与依据" :aria-busy="reference.loading">
          <p v-if="reference.loading" class="reference-loading" role="status">正在加载参考资料…</p>
          <div v-else-if="reference.error" class="reference-error" role="alert"><span>{{ reference.error }}</span><button type="button" @click="$emit('retry-reference', item.id)">重试</button></div>
          <template v-else-if="reference.data">
            <p v-if="notice" class="reference-notice">{{ notice }}</p>
            <dl class="reference-values"><div v-for="section in referenceSections" :key="section.key"><dt>{{ section.label }}</dt><dd>{{ formatReferenceValue(reference.data[section.key]) }}</dd></div></dl>
          </template>
        </section>
      </template>
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import { answerStatusLabel, formatReferenceValue, isAnswered, kindLabel, referenceNotice, safeSourceUrl, scopeLabel, sourceKindLabel } from './presentation.js'

const props = defineProps({
  item: { type: Object, required: true },
  ordinal: { type: Number, required: true },
  canViewReference: { type: Boolean, default: false },
  reference: { type: Object, default: null },
})
defineEmits(['toggle-reference', 'retry-reference'])
const referenceId = computed(() => `bank-reference-${props.item.id}`)
const notice = computed(() => referenceNotice(props.reference?.data?.answer_status || props.item.answer_status))
const options = computed(() => (Array.isArray(props.item.options) ? props.item.options : []).map((option, index) => {
  if (typeof option === 'string') return { key: String.fromCharCode(65 + index), text: option.replace(/^[A-Z][.、．\s]+/, '') }
  return { key: String(option?.key || String.fromCharCode(65 + index)), text: String(option?.text || '') }
}).filter(option => option.text))
const referenceSections = computed(() => {
  const sections = [{ key: 'answer', label: '参考答案' }]
  if (props.reference?.data?.partial_answer != null) sections.push({ key: 'partial_answer', label: '部分参考内容（待核验）' })
  return [...sections, { key: 'explanation', label: '解析说明' }, { key: 'answer_evidence', label: '答案依据' }]
})
</script>

<style scoped>
.bank-question{display:flex;gap:20px;padding:25px 28px;border:1px solid #dce6ef;border-radius:9px;background:#fff}
.question-number{padding-top:2px;min-width:30px;font:24px/1.3 Georgia,serif;color:#9aafbf}
.question-content{flex:1;min-width:0}.question-meta{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;align-items:center}.question-tags{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.kind-tag,.status-tag,.scope-label,.image-label{display:inline-block;font-size:12px;line-height:1.5;padding:3px 8px;border-radius:4px}.kind-tag{color:#006ca8;background:#edf6fc}.status-tag{color:#556d7e;background:#f0f4f7}.status-tag.pending{color:#8a6128;background:#fff5e5}.scope-label{color:#546c7d;border:1px solid #dce6ef}.scope-label.station-scope{color:#8b622f;border-color:#e9d6b6;background:#fffdf7}.image-label{color:#6b7c87;background:#f5f6f7}.question-id{font-size:12px;color:#687f91;overflow-wrap:anywhere}
.question-stem{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.95;font-size:16px;margin:18px 0;color:#183b58}.question-options{list-style:none;padding:0;margin:0 0 20px;display:grid;gap:8px}.question-options li{display:flex;align-items:baseline;gap:12px;background:#f7f9fc;border:1px solid #e7edf3;border-radius:5px;padding:10px 14px;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.8;font-size:14px}.option-key{font-weight:600;color:#59778e;flex-shrink:0;min-width:16px}
.question-source{display:flex;gap:14px;border-top:1px solid #edf1f5;padding-top:14px;color:#62798c;font-size:12px;line-height:1.85;overflow-wrap:anywhere}.source-label{flex-shrink:0;color:#718796}.question-source p{margin:0}.question-source a{display:inline-block;color:#0075b7;margin-left:8px}.source-details{display:flex;gap:14px;flex-wrap:wrap;color:#6c8293;margin-top:2px!important}
.reference-toggle{display:flex;align-items:center;gap:22px;padding:9px 0;margin-top:11px;border:0;background:transparent;color:#0075b7;font:inherit;font-size:13px;cursor:pointer}.reference-toggle:hover{text-decoration:underline}.reference-toggle>span:last-child{font-size:19px;line-height:1}.reference-panel{padding:18px 20px;background:#f4f8fb;border:1px solid #dce7f0;border-radius:6px;margin-top:4px}.reference-loading{color:#62798c;margin:0;font-size:14px}.reference-notice{margin:0 0 16px;padding:10px 13px;border-left:3px solid #c19856;background:#fff8e9;color:#805c28;font-size:13px;line-height:1.85}.reference-values{margin:0}.reference-values>div+div{margin-top:17px}.reference-values dt{font-size:12px;color:#60798c;margin-bottom:5px}.reference-values dd{white-space:pre-wrap;overflow-wrap:anywhere;font-size:14px;line-height:1.9;margin:0;color:#25475f}.reference-error{display:flex;justify-content:space-between;align-items:center;gap:12px;color:#a43f36;font-size:14px}.reference-error button{border:1px solid #c7d8e6;background:#fff;color:#0075b7;padding:7px 12px;border-radius:4px;cursor:pointer;flex-shrink:0}
:is(a,button):focus-visible{outline:3px solid #0075b7;outline-offset:4px}@media(max-width:700px){.bank-question{padding:19px 15px;gap:12px}.question-number{font-size:20px;min-width:23px}.question-meta{gap:9px}.question-stem{font-size:15px;margin:15px 0}.question-options li{padding:9px 11px;gap:9px}.question-source{gap:10px}.reference-panel{padding:14px 12px}.reference-error{align-items:flex-start;flex-direction:column}}
</style>
