<template>
  <section class="objective-paper" aria-label="客观题试卷">
    <article v-for="(question, index) in questions" :key="question.id" :id="`paper-question-${question.id}`" class="paper-question" tabindex="-1">
      <header><h3>第 {{ index + 1 }} 题 <span>{{ objectiveKinds[question.kind] }}</span></h3><span>{{ question.points }} 分</span></header>
      <p class="paper-stem">{{ question.stem }}</p>
      <img v-for="figure in question.images || []" :key="figure.src" :src="figure.src" :alt="figure.alt" class="paper-figure" />
      <fieldset :disabled="disabled"><legend class="sr-only">第 {{ index + 1 }} 题答案</legend>
        <template v-if="['choice','multi'].includes(question.kind)">
          <label v-for="option in question.options" :key="option.key" class="paper-option">
            <input :type="question.kind === 'multi' ? 'checkbox' : 'radio'" :name="`${inputGroup}-${question.id}`" :value="option.key"
              :checked="question.kind === 'multi' ? (answers[question.id] || []).includes(option.key) : answers[question.id] === option.key"
              @change="select(question, option.key, $event.target.checked)" />
            <span>{{ option.key }}. {{ option.text }}</span>
          </label>
        </template>
        <template v-else-if="question.kind === 'true_false'">
          <label v-for="value in [true,false]" :key="String(value)" class="paper-option"><input type="radio" :name="`${inputGroup}-${question.id}`" :checked="answers[question.id] === value" @change="change(question.id, value)" /><span>{{ value ? '正确' : '错误' }}</span></label>
        </template>
        <template v-else-if="question.kind === 'cell'">
          <label v-for="(_, blank) in question.blank_count" :key="blank" class="paper-blank">第 {{ blank + 1 }} 空<input type="text" :aria-label="`第${index + 1}题第${blank + 1}空`" maxlength="2000" :value="answers[question.id]?.[blank] || ''" @input="fillBlank(question, blank, $event.target.value)" /></label>
        </template>
      </fieldset>
      <div v-if="feedback(question.id)" class="paper-feedback" :class="{correct:feedback(question.id).correct}">
        <strong>{{ feedback(question.id).correct ? '回答正确' : '回答错误或未答' }} · 得分 {{ feedback(question.id).earned }} / {{ question.points }}</strong>
        <p>{{ answerLabel }}：{{ answerText(feedback(question.id).submitted_answer) }}</p><p>标准答案：{{ answerText(feedback(question.id).correct_answer) }}</p>
        <p v-if="question.kind === 'multi' && !feedback(question.id).correct">{{ multiDifference(feedback(question.id)) }}</p>
        <p v-if="feedback(question.id).blank_results?.length">{{ feedback(question.id).blank_results.map((correct,index)=>`第${index+1}空${correct?'正确':'错误或未填'}`).join('；') }}</p>
        <p v-if="feedback(question.id).explanation || feedback(question.id).answer_evidence">{{ feedback(question.id).explanation || feedback(question.id).answer_evidence }}</p>
      </div>
    </article>
  </section>
</template>
<script setup>
import { useId } from 'vue'
import { objectiveKinds, answerText } from '@/domain/objectiveExams'
const props = defineProps({ questions:{type:Array,default:()=>[]}, answers:{type:Object,default:()=>({})}, disabled:Boolean, evaluation:Object, answerLabel:{type:String,default:'本人答案'} })
const emit = defineEmits(['answer'])
const inputGroup = useId()
const change = (id, value) => emit('answer', id, value)
function select(question, key, checked) {
  if (question.kind === 'choice') return change(question.id, key)
  const values = new Set(props.answers[question.id] || [])
  if (checked) values.add(key); else values.delete(key)
  change(question.id, [...values])
}
function fillBlank(question, index, value) {
  const values = [...(props.answers[question.id] || Array(question.blank_count).fill(''))]
  values[index] = value; change(question.id, values)
}
const feedback = id => props.evaluation?.items.find(item => item.question_id === id)
function multiDifference(result) {
  const correct = [...result.correct_answer], submitted = result.submitted_answer || []
  const missing = correct.filter(key=>!submitted.includes(key)), extra = submitted.filter(key=>!correct.includes(key))
  return [missing.length ? `漏选：${missing.join('、')}` : '', extra.length ? `误选：${extra.join('、')}` : ''].filter(Boolean).join('；')
}
</script>
<style scoped>
.paper-question{padding:24px;background:#fff;border:1px solid #dfe7ef;margin-bottom:16px;scroll-margin-top:20px}.paper-question header{display:flex;justify-content:space-between;gap:16px;align-items:center}.paper-question h3{margin:0;font-size:18px}.paper-question h3 span{font-size:13px;font-weight:400;color:#586f82;margin-left:12px}.paper-stem{white-space:pre-wrap;line-height:1.9;font-size:16px;overflow-wrap:anywhere}.paper-question fieldset{border:0;padding:0;margin:0;display:grid;gap:10px}.paper-option{display:flex;gap:12px;align-items:baseline;padding:12px 14px;border:1px solid #dfe7ef;line-height:1.7;cursor:pointer}.paper-option:has(input:checked){background:#edf4fa;border-color:#0075b7}.paper-option:has(input:focus-visible){outline:2px solid #0075b7;outline-offset:2px}.paper-option input{accent-color:#093278;flex-shrink:0}.paper-blank{display:flex;align-items:center;gap:14px}.paper-blank input{min-width:0;flex:1;padding:10px;border:1px solid #aabcca;border-radius:4px;font:inherit}.paper-figure{max-width:100%;max-height:400px;object-fit:contain;margin-bottom:16px}.paper-feedback{background:#fff3ed;border-left:3px solid #b54732;padding:16px;margin-top:16px;line-height:1.8;overflow-wrap:anywhere;white-space:pre-wrap}.paper-feedback.correct{background:#eef7f1;border-color:#17815b}.paper-feedback p{margin:8px 0 0}.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}@media(max-width:650px){.paper-question{padding:16px}.paper-blank{align-items:stretch;flex-direction:column;gap:6px}}
</style>
