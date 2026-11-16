<template>
  <article
    class="study-question"
    :id="`study-question-${question.id}`"
    :aria-label="`第 ${number} 题`"
    tabindex="-1"
  >
    <header class="question-top">
      <div>
        <span class="question-number">{{
          String(number).padStart(2, '0')
        }}</span
        ><span class="kind-label">{{ kindLabel(question.kind) }}</span
        ><span
          class="history-state"
          :class="{ mastered: entry.ever_correct }"
          >{{ studyState(entry) }}</span
        >
      </div>
      <button
        class="mark-button"
        :class="{ marked: entry.marked }"
        :aria-pressed="entry.marked"
        :disabled="entry.marking"
        @click="$emit('bookmark', entry)"
      >
        {{ entry.marked ? '★ 已标记' : '☆ 标记' }}
      </button>
    </header>
    <div v-if="question.images?.length" class="question-figures">
      <a
        v-for="figure in question.images"
        :key="figure.src"
        :href="figure.src"
        target="_blank"
        rel="noopener"
        :aria-label="`放大查看${figure.alt}`"
        ><img :src="figure.src" :alt="figure.alt" loading="lazy"
      /></a>
    </div>
    <h3 class="question-stem">{{ question.stem }}</h3>
    <form @submit.prevent="$emit('submit', entry)">
      <fieldset
        :disabled="Boolean(feedback) || entry.submitting"
        class="answer-fields"
      >
        <legend class="sr-only">第 {{ number }} 题答案</legend>
        <template
          v-if="question.kind === 'choice' || question.kind === 'multi'"
        >
          <label
            v-for="option in question.options"
            :key="option.key"
            class="answer-option"
            :class="optionClass(option.key)"
          >
            <input
              v-model="entry.draft"
              :type="question.kind === 'multi' ? 'checkbox' : 'radio'"
              :name="`answer-${question.id}`"
              :value="option.key"
            />
            <span class="option-key">{{ option.key }}</span><span>{{
              option.text
            }}</span>
            <span
              v-if="feedback && optionClass(option.key)"
              class="option-result"
              >{{
                optionClass(option.key) === 'answer-correct'
                  ? '✓ 正确选项'
                  : '× 误选'
              }}</span
            >
          </label>
        </template>
        <template v-else-if="isBooleanQuestion(question)">
          <label
            v-for="value in [true, false]"
            :key="String(value)"
            class="answer-option"
            :class="booleanClass(value)"
            ><input
              v-model="entry.draft"
              type="radio"
              :name="`answer-${question.id}`"
              :value="value"
            /><span>{{ value ? '正确' : '错误' }}</span
            ><span
              v-if="feedback && booleanClass(value)"
              class="option-result"
              >{{
                booleanClass(value) === 'answer-correct'
                  ? '✓ 正确答案'
                  : '× 误选'
              }}</span
            ></label
          >
        </template>
        <template v-else-if="question.kind === 'cell'">
          <label
            v-for="(_, index) in blankCount(question)"
            :key="index"
            class="blank-answer"
            ><span>第 {{ index + 1 }} 空</span
            ><input
              v-model="entry.draft[index]"
              type="text"
              :aria-label="`第 ${number} 题，第 ${index + 1} 空答案`"
              autocomplete="off"
              maxlength="1000"
            /><span
              v-if="feedback?.blank_results?.[index] != null"
              :class="
                feedback.blank_results[index]
                  ? 'answer-correct'
                  : 'answer-wrong'
              "
              >{{ feedback.blank_results[index] ? '✓ 正确' : '× 错误' }}</span
            ></label
          >
        </template>
      </fieldset>
      <footer v-if="!feedback" class="question-actions">
        <button
          class="primary-button"
          type="submit"
          :disabled="entry.submitting || !hasAnswer(question, entry.draft)"
        >
          {{ entry.submitting ? '正在提交…' : '提交本题' }}</button
        ><span>{{
          question.kind === 'multi' ? '可选择多个选项' : '提交后查看答案与解析'
        }}</span>
      </footer>
    </form>
    <div
      v-if="feedback"
      class="feedback-panel"
      :class="feedback.correct ? 'is-correct' : 'is-wrong'"
    >
      <div class="feedback-heading">
        <strong role="status">{{
          feedback.correct ? '✓ 回答正确' : '× 回答错误'
        }}</strong
        ><button @click="$emit('retry', entry)">重新练习</button>
      </div>
      <p>
        <span>正确答案</span>{{ answerText(question, feedback.correct_answer) }}
      </p>
      <details :open="!feedback.correct">
        <summary>答案解析</summary>
        <div>
          {{
            feedback.explanation ||
            feedback.answer_evidence ||
            '本题暂未提供文字解析，可结合教材复习。'
          }}
        </div>
      </details>
    </div>
    <p v-if="entry.error" class="question-error" role="alert">
      {{ entry.error }}
    </p>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import {
  answerKeys,
  answerText,
  blankCount,
  hasAnswer,
  isBooleanQuestion,
} from './useChapterPractice.js'
import { kindLabel } from './presentation.js'
import { studyState } from './useChapterStudy.js'
const props = defineProps({
  entry: { type: Object, required: true },
  number: { type: Number, required: true },
})
defineEmits(['submit', 'bookmark', 'retry'])
const question = computed(() => props.entry.question)
const feedback = computed(() =>
  props.entry.attempt?.submitted ? props.entry.attempt.feedback : null,
)
function optionClass(key) {
  if (!feedback.value) return ''
  if (answerKeys(question.value, feedback.value.correct_answer).includes(key))
    return 'answer-correct'
  return answerKeys(question.value, feedback.value.submitted_answer).includes(
    key,
  )
    ? 'answer-wrong'
    : ''
}
function booleanClass(value) {
  if (!feedback.value) return ''
  if (feedback.value.correct_answer === value) return 'answer-correct'
  return feedback.value.submitted_answer === value ? 'answer-wrong' : ''
}
</script>

<style scoped>
.study-question {
  background: #fff;
  border: 1px solid #dfe7ef;
  border-radius: 8px;
  padding: 26px 30px;
  scroll-margin-top: 24px;
  min-width: 0;
}
.study-question:focus {
  outline: 2px solid #0075b7;
  outline-offset: 3px;
}
.question-top,
.question-top > div {
  display: flex;
  align-items: center;
  gap: 12px;
}
.question-top {
  justify-content: space-between;
}
.question-number {
  font-size: 22px;
  font-weight: 650;
  color: #19334d;
  font-variant-numeric: tabular-nums;
}
.kind-label {
  padding: 4px 9px;
  border-radius: 4px;
  background: #edf5fa;
  color: #0075b7;
  font-size: 12px;
}
.history-state {
  color: #607388;
  font-size: 12px;
}
.history-state.mastered {
  color: #237449;
}
.mark-button {
  border: 0;
  padding: 6px 0;
  color: #607388;
  background: transparent;
  white-space: nowrap;
}
.mark-button.marked {
  color: #8b6b16;
}
.question-stem {
  font-size: 17px;
  font-weight: 500;
  line-height: 1.95;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  margin: 23px 0;
}
.answer-fields {
  border: 0;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 10px;
  min-width: 0;
}
.answer-option {
  display: flex;
  align-items: baseline;
  gap: 12px;
  border: 1px solid #dfe7ef;
  border-radius: 5px;
  padding: 13px 16px;
  font-size: 14px;
  line-height: 1.8;
  cursor: pointer;
  overflow-wrap: anywhere;
}
.answer-option input {
  flex-shrink: 0;
  accent-color: #0075b7;
}
.answer-option:has(input:checked) {
  background: #edf6fc;
  border-color: #75afd1;
}
.option-key {
  font-weight: 600;
}
.option-result {
  margin-left: auto;
  flex-shrink: 0;
  font-size: 12px;
}
.answer-fields:disabled .answer-option {
  cursor: default;
}
.answer-correct {
  color: #237449;
}
.answer-wrong {
  color: #ad413a;
}
.answer-option.answer-correct {
  border-color: #9bcbb0;
  background: #f2faf5;
}
.answer-option.answer-wrong {
  border-color: #e0a29c;
  background: #fff5f3;
}
.blank-answer {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 13px;
  flex-wrap: wrap;
}
.blank-answer > span:first-child {
  color: #607388;
}
.blank-answer input {
  flex: 1;
  min-width: 120px;
  border: 1px solid #c9d9e6;
  border-radius: 4px;
  padding: 12px;
  color: #19334d;
  background: #fafcfe;
}
.blank-answer input:disabled {
  color: #19334d;
  -webkit-text-fill-color: #19334d;
  opacity: 1;
}
.question-actions {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 22px;
}
.question-actions > span {
  color: #607388;
  font-size: 12px;
}
button {
  font: inherit;
  font-size: 13px;
  padding: 9px 16px;
  border: 1px solid #ccdae6;
  border-radius: 5px;
  background: #fff;
  color: #315b78;
  cursor: pointer;
}
button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.primary-button {
  color: #fff;
  background: #0075b7;
  border-color: #0075b7;
}
.feedback-panel {
  margin-top: 24px;
  border-top: 1px solid #e2eaf1;
  padding-top: 20px;
  font-size: 14px;
  line-height: 1.9;
}
.feedback-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 15px;
}
.is-correct strong {
  color: #237449;
}
.is-wrong strong {
  color: #ad413a;
}
.feedback-heading button {
  padding: 6px 12px;
}
.feedback-panel p {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.feedback-panel p > span {
  color: #607388;
  margin-right: 15px;
  font-size: 12px;
}
.feedback-panel summary {
  cursor: pointer;
  color: #0075b7;
}
.feedback-panel details > div {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  color: #52677e;
  padding-top: 10px;
}
.question-error {
  color: #ad413a;
  background: #fff3f1;
  padding: 12px;
  font-size: 13px;
  line-height: 1.8;
}
.question-figures {
  display: grid;
  gap: 12px;
  margin-top: 20px;
}
.question-figures img {
  max-width: 100%;
  height: auto;
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
}
.study-question :is(button, input, summary):focus-visible {
  outline: 3px solid #0075b7;
  outline-offset: 3px;
}
@media (max-width: 650px) {
  .study-question {
    padding: 20px 16px;
  }
  .question-top > div {
    gap: 8px;
    flex-wrap: wrap;
  }
  .question-stem {
    font-size: 16px;
  }
  .answer-option {
    padding: 12px 10px;
    gap: 8px;
    flex-wrap: wrap;
  }
  .option-result {
    width: 100%;
    padding-left: 28px;
  }
  .question-actions {
    flex-wrap: wrap;
    gap: 10px;
  }
  .history-state {
    font-size: 11px;
  }
}
</style>
