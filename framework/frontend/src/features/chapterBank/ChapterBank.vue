<template>
  <main class="chapter-bank" :class="{ 'is-practicing': Boolean(chapterId) }">
    <header v-if="!chapterId" class="bank-heading">
      <div><h1>客观题库</h1></div><router-link class="all-questions-link" to="/student/chapter-bank/all">查看全部题目</router-link>
      <router-link v-if="chapterId" class="back-link" to="/student/chapter-bank">← 返回六章目录</router-link>
    </header>
    <div v-if="chaptersError" class="bank-error" role="alert"><span>{{ chaptersError }}</span><button @click="loadChapters">重试加载目录</button></div>
    <template v-if="!chapterId">
      <section v-loading="chaptersLoading" class="chapter-grid" aria-label="章节目录" :aria-busy="chaptersLoading">
        <article v-for="chapter in chapters" :key="chapter.id" class="chapter-card">
          <router-link class="chapter-main-link" :to="chapterPath(chapter.id)">
            <div class="card-top"><span class="chapter-number">{{ String(chapter.id).padStart(2, '0') }}</span></div>
            <h3>{{ chapter.title }}</h3>
            <div class="card-bottom"><span>开始练习</span><span aria-hidden="true">→</span></div>
          </router-link>
          <router-link class="marked-entry" :to="chapterPath(chapter.id, true)"><span aria-hidden="true">☆</span> 练习标记题目 <span>{{ chapter.bookmarked }} 题</span></router-link>
        </article>
      </section>
      <el-empty v-if="!chaptersLoading && !chaptersError && !chapters.length" description="暂无章节资料" />
    </template>
    <template v-else>
      <div class="practice-heading"><router-link to="/student/chapter-bank/all">查看全部题目</router-link><router-link to="/student/chapter-bank">← 章节目录</router-link><router-link v-if="markedOnly" :to="chapterPath(chapterId)">全部题目</router-link></div>
      <div v-if="practiceError" class="bank-error" role="alert"><span>{{ practiceError }}</span><button v-if="!current || current.attempt.submitted" :disabled="busy" @click="practice.next">重试抽题</button></div>
      <div v-if="empty" class="empty-panel" role="status"><span class="empty-symbol" aria-hidden="true">✓</span><h2>{{ empty }}</h2><p>{{ markedOnly ? '可先在本章练习中标记想要复习的题目。' : '已核验题目会陆续加入练习。你也可以返回目录选择其他章节。' }}</p><div><router-link v-if="markedOnly" :to="chapterPath(chapterId)">返回全部练习</router-link><button v-else-if="current" :disabled="busy" @click="practice.restart">重新随机练习本章</button><router-link to="/student/chapter-bank">返回六章目录</router-link></div></div>
      <div v-loading="busy && !current" class="practice-stage" :aria-busy="busy">
        <div v-if="current" :key="current.attempt.id" class="question-layout">
          <article class="question-paper">
            <div class="question-meta"><span class="kind-label">{{ questionKind }}</span></div>
            <div v-if="question.images?.length" class="question-figures"><a v-for="figure in question.images" :key="figure.src" :href="figure.src" target="_blank" rel="noopener" :aria-label="`放大查看${figure.alt}`"><img :src="figure.src" :alt="figure.alt"></a></div>
            <h2 class="question-stem">{{ question.stem }}</h2>
            <form @submit.prevent="practice.submit">
              <fieldset :disabled="current.attempt.submitted || busy" class="answer-fields"><legend class="sr-only">填写本题答案</legend>
                <template v-if="question.kind === 'choice' || question.kind === 'multi'">
                  <label v-for="option in question.options" :key="option.key" class="answer-option" :class="optionClass(option.key)"><input v-model="current.draft" :type="question.kind === 'multi' ? 'checkbox' : 'radio'" :name="`answer-${current.attempt.id}`" :value="option.key"><span class="option-key">{{ option.key }}</span><span>{{ option.text }}</span><span v-if="optionClass(option.key) === 'answer-correct'" class="option-result" aria-label="正确选项">✓</span><span v-else-if="optionClass(option.key) === 'answer-wrong'" class="option-result" aria-label="误选">×</span></label>
                </template>
                <template v-else-if="isBooleanQuestion(question)">
                  <label v-for="value in [true, false]" :key="String(value)" class="answer-option" :class="booleanClass(value)"><input v-model="current.draft" type="radio" :name="`answer-${current.attempt.id}`" :value="value"><span>{{ value ? '正确' : '错误' }}</span><span v-if="booleanClass(value) === 'answer-correct'" class="option-result" aria-label="正确答案">✓</span><span v-else-if="booleanClass(value) === 'answer-wrong'" class="option-result" aria-label="本次作答错误">×</span></label>
                </template>
                <template v-else-if="question.kind === 'cell'">
                  <label v-for="(_, blankIndex) in blankCount(question)" :key="blankIndex" class="blank-answer" :class="[blankClass(blankIndex), { 'single-blank': blankCount(question) === 1 }]"><span v-if="blankCount(question) > 1">{{ blankIndex + 1 }}</span><input v-model="current.draft[blankIndex]" type="text" :aria-label="`第 ${blankIndex + 1} 空答案`" autocomplete="off"><span v-if="feedback?.blank_results?.[blankIndex] != null" class="blank-result" :aria-label="feedback.blank_results[blankIndex] ? '正确' : '错误'">{{ feedback.blank_results[blankIndex] ? '✓' : '×' }}</span></label>
                </template>
              </fieldset>
              <div v-if="!current.attempt.submitted" class="submit-row"><button class="primary-button" type="submit" :disabled="!canSubmit">{{ current.submitting ? '正在提交…' : '提交答案' }}</button></div>
            </form>
            <p v-if="feedback" class="sr-only" role="status">{{ feedback.correct ? '回答正确' : '回答错误' }}</p>
            <div v-if="feedback && !feedback.correct" class="correct-answer"><span>正确答案</span><p>{{ answerText(question, feedback.correct_answer) }}</p></div>
            <div v-if="feedback" class="analysis-area"><button type="button" class="analysis-toggle" :aria-expanded="explanationOpen" aria-controls="practice-explanation" @click="explanationOpen = !explanationOpen">{{ explanationOpen ? '收起解析' : '查看解析' }}</button><section v-if="explanationOpen" id="practice-explanation" class="analysis-content" aria-label="本题解析">{{ feedback.explanation || feedback.answer_evidence || '暂无解析。' }}</section></div>
          </article>
        </div>
        <p v-else-if="busy" class="loading-message" role="status">正在随机抽取一道题…</p>
      </div>
      <nav v-if="current" class="practice-nav" aria-label="练习题目操作"><button :disabled="busy || index <= 0" @click="practice.previous">← 上一题</button><button class="bookmark-button" :class="{ marked: current.attempt.marked }" :aria-pressed="current.attempt.marked" :disabled="marking" @click="practice.toggleBookmark"><span aria-hidden="true">{{ current.attempt.marked ? '★' : '☆' }}</span> {{ marking ? '保存中…' : current.attempt.marked ? '已标记题目' : '标记题目' }}</button><button class="primary-button" :disabled="busy || !current.attempt.submitted" @click="practice.next">下一题 →</button></nav>
    </template>
  </main>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import request from '@/utils/request'
import { answerKeys, answerText, blankCount, createChapterPractice, hasAnswer, isBooleanQuestion } from './useChapterPractice.js'
import { errorText, kindLabel } from './presentation.js'

const route = useRoute()
const chapterId = computed(() => String(route.params.chapterId || ''))
const markedOnly = computed(() => route.query.marked === '1')
const chapters = ref([]), chaptersLoading = ref(false), chaptersError = ref('')
let chapterRequest = 0
const currentChapter = computed(() => chapters.value.find(chapter => String(chapter.id) === chapterId.value))
const chapterPath = (id, marked = false) => ({ path: `/student/chapter-bank/${id}`, query: marked ? { marked: '1' } : {} })
const practice = createChapterPractice({ post: (...args) => request.post(...args), put: (...args) => request.put(...args), onBookmarkChange: loadChapters })
const { current, index, busy, marking, error: practiceError, empty } = practice
const question = computed(() => current.value?.attempt.question || {})
const feedback = computed(() => current.value?.attempt.submitted ? current.value.attempt.feedback : null)
const explanationOpen = ref(false)
watch(() => current.value?.attempt.id, () => { explanationOpen.value = false })
const questionKind = computed(() => isBooleanQuestion(question.value) ? '判断题' : kindLabel(question.value.kind))
const canSubmit = computed(() => current.value && !busy.value && !current.value.attempt.submitted && hasAnswer(question.value, current.value.draft))
const correctKeys = computed(() => answerKeys(question.value, feedback.value?.correct_answer))
function optionClass(key) {
  if (!feedback.value) return ''
  if (correctKeys.value.includes(key)) return 'answer-correct'
  const answer = feedback.value.submitted_answer
  return (Array.isArray(answer) ? answer.includes(key) : answer === key) ? 'answer-wrong' : ''
}
function booleanClass(value) {
  if (!feedback.value) return ''
  if (feedback.value.correct_answer === value) return 'answer-correct'
  return feedback.value.submitted_answer === value ? 'answer-wrong' : ''
}
function blankClass(index) {
  const result = feedback.value?.blank_results?.[index]
  return result == null ? '' : result ? 'answer-correct' : 'answer-wrong'
}
async function loadChapters() {
  const serial = ++chapterRequest
  chaptersLoading.value = true; chaptersError.value = ''
  try {
    const result = await request.get('/chapter-bank/practice/chapters')
    if (serial === chapterRequest) chapters.value = Array.isArray(result) ? result : []
  } catch (failure) { if (serial === chapterRequest) chaptersError.value = errorText(failure, '目录加载失败，请重试。') }
  finally { if (serial === chapterRequest) chaptersLoading.value = false }
}
watch([chapterId, markedOnly], ([id, marked]) => practice.setChapter(id, marked), { immediate: true })
loadChapters()
onBeforeUnmount(() => { chapterRequest++; practice.dispose() })
</script>

<style scoped>
.all-questions-link{padding:10px 18px;border:1px solid #bad5e5;border-radius:6px;background:white;color:#0075b7;font-size:14px}

.chapter-bank{max-width:1320px;margin:auto;color:#183b58;min-width:0;padding-bottom:20px}.bank-heading{display:flex;justify-content:space-between;align-items:center;gap:16px;margin-bottom:16px}.eyebrow{font-size:11px;letter-spacing:1.4px;color:#0075b7}.bank-heading h1{font-size:28px;line-height:1.5;font-weight:600;margin:4px 0 0}.back-link{flex-shrink:0;color:#0075b7;font-size:14px}.section-heading{display:flex;justify-content:space-between;align-items:baseline;gap:12px;margin-bottom:12px}.section-heading h2{font-size:19px;font-weight:500;margin:0}.section-heading>span{font-size:13px;color:#718799}
.chapter-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;min-height:120px}.chapter-card{background:#fff;border:1px solid #dae5ef;border-top:3px solid #c6aa70;border-radius:10px;overflow:hidden;transition:border-color .15s,box-shadow .15s}.chapter-card:hover{border-color:#85aec9;box-shadow:0 5px 18px #174c7410}.chapter-main-link{display:block;color:inherit;text-decoration:none;padding:16px 18px 0}.card-top{display:flex;justify-content:space-between;align-items:center;gap:10px}.chapter-number{font:30px Georgia,serif;color:#adc1cf}.chapter-card h3{font-size:19px;font-weight:500;line-height:1.5;margin:10px 0 8px}.card-bottom{display:flex;justify-content:space-between;gap:12px;border-top:1px solid #e5edf4;padding:10px 0;font-size:13px;color:#0075b7}.marked-entry{display:flex;align-items:center;gap:7px;background:#f8fafc;border-top:1px solid #e8eef4;padding:9px 18px;font-size:12px;color:#667e91;text-decoration:none}.marked-entry>span:last-child{margin-left:auto}.marked-entry:hover{background:#f0f6fb;color:#0075b7}
.practice-heading{display:flex;justify-content:space-between;gap:15px;margin:0 0 16px;font-size:13px;color:#718799}.practice-heading a{color:#0075b7}.practice-stage{min-height:120px}.question-layout{display:grid;grid-template-columns:minmax(0,1fr);gap:24px;align-items:start}.question-layout.with-note{grid-template-columns:minmax(0,1fr) 320px}.question-paper{background:#fff;border:1px solid #dce6ee;border-radius:10px;padding:32px 36px;min-width:0}.question-meta{display:flex;align-items:center;gap:13px;flex-wrap:wrap;color:#7c8fa0;font-size:12px}.kind-label{color:#0075b7;background:#edf6fc;border:1px solid #d8eaf5;padding:5px 10px;border-radius:4px}.question-id{margin-left:auto;font-size:11px;overflow-wrap:anywhere}.question-stem{font-size:20px;line-height:1.95;font-weight:500;white-space:pre-wrap;overflow-wrap:anywhere;margin:25px 0 27px}.answer-fields{padding:0;margin:0;border:0;min-width:0;display:grid;gap:13px}.answer-option{display:flex;align-items:baseline;gap:13px;padding:17px 19px;border:1px solid #dce6ef;border-radius:7px;background:#fcfdfe;font-size:15px;line-height:1.8;cursor:pointer;overflow-wrap:anywhere}.answer-option:has(input:checked){border-color:#6ea7cc;background:#f0f7fc}.answer-option input{flex-shrink:0;accent-color:#0075b7}.option-key{font-weight:600}.option-result{font-size:11px;margin-left:auto;flex-shrink:0}.answer-fields:disabled .answer-option{cursor:default}.answer-fields:disabled input{opacity:1}.input-hint{font-size:13px;color:#718799;margin:0 0 7px;line-height:1.8}.blank-answer{display:flex;align-items:center;gap:15px;font-size:14px;color:#60798c}.blank-answer>span:first-child{flex-shrink:0}.blank-answer input{width:100%;min-width:0;background:#fbfcfe;border:0;border-bottom:2px solid #bbcfde;border-radius:3px;padding:13px 11px;color:#183b58;font:inherit;line-height:1.6}.blank-answer input:disabled{background:#f6f9fb;color:inherit;-webkit-text-fill-color:currentColor;opacity:1}.blank-result{font-size:12px;flex-shrink:0}.submit-row{display:flex;align-items:center;gap:17px;flex-wrap:wrap;margin-top:29px}.submit-row>span{color:#8a9aa7;font-size:12px}
button{font:inherit;font-size:13px;border:1px solid #cfdde8;background:#fff;color:#315b78;padding:11px 20px;border-radius:6px;cursor:pointer;line-height:1.5}button:hover:not(:disabled){border-color:#0075b7;color:#0075b7}button:disabled{opacity:.45;cursor:not-allowed}.primary-button{background:#0075b7;color:#fff;border-color:#0075b7}.primary-button:hover:not(:disabled){background:#00679f;color:#fff}.answer-feedback{margin-top:29px;padding:18px 20px;border:1px solid currentColor;border-radius:7px}.answer-feedback strong{font-size:17px}.answer-feedback p{font-size:13px;line-height:1.85;margin:8px 0 0}.brief-explanation{white-space:pre-wrap}.answer-correct{color:#237449!important}.answer-option.answer-correct{border-color:#94c7aa!important;background:#f3faf5!important}.answer-wrong{color:#b14340!important}.answer-option.answer-wrong{border-color:#dea4a0!important;background:#fff6f5!important}.blank-answer.answer-correct input{border-color:#4eaa75}.blank-answer.answer-wrong input{border-color:#cc7069}.answer-feedback.answer-correct{background:#f3faf5;border-color:#b9dcc7}.answer-feedback.answer-wrong{background:#fff7f5;border-color:#ecc6c2}.question-source{display:flex;flex-wrap:wrap;gap:12px;border-top:1px solid #e9eff4;margin-top:30px;padding-top:17px;font-size:11px;color:#8b9ba8;line-height:1.8;overflow-wrap:anywhere}.question-source a{color:#54829e}
.correction-note{position:relative;background:#fffdf2;border:1px solid #e6dfb8;border-radius:3px 8px 8px 3px;padding:29px 24px 25px;box-shadow:3px 5px 0 #e7dfc42a;transform:rotate(.4deg);animation:note-arrive .3s ease-out}.correction-note:before{content:'';width:65px;height:20px;background:#e1c98455;position:absolute;top:-9px;left:calc(50% - 32px);transform:rotate(-5deg)}.note-eyebrow{font-size:11px;color:#9c8c54;letter-spacing:2px}.correction-note h3{font-size:23px;font-family:KaiTi,STKaiti,serif;margin:15px 0 27px;color:#665d3d;font-weight:500}.note-answer>span{color:#237449;font-size:12px}.note-answer p{color:#237449;font-size:17px;font-family:KaiTi,STKaiti,serif;line-height:2.1;white-space:pre-wrap;overflow-wrap:anywhere;text-decoration:underline;text-decoration-color:#6da87580;text-underline-offset:7px;text-decoration-thickness:1.5px;margin:10px 0 25px}.note-explanation h4{color:#877344;font-size:13px;font-weight:500;margin:0 0 12px}.note-explanation p{font-size:14px;line-height:2;color:#72664b;white-space:pre-wrap;overflow-wrap:anywhere;margin:0}.note-evidence{border-top:1px dashed #dfd5b2;margin:21px 0 0;padding-top:15px;color:#958769;font-size:11px;line-height:1.9;white-space:pre-wrap;overflow-wrap:anywhere}
.practice-nav{position:sticky;bottom:12px;z-index:4;display:flex;justify-content:space-between;gap:14px;margin-top:25px;padding:16px 20px;background:#fffffff2;border:1px solid #dbe6ef;border-radius:9px;box-shadow:0 4px 18px #234b6610;backdrop-filter:blur(8px)}.bookmark-button{margin:auto;color:#8b783f}.bookmark-button.marked{background:#fff9e5;border-color:#d8c38a;color:#8d7229}.bank-error{display:flex;justify-content:space-between;align-items:center;gap:12px;background:#fff2f0;border:1px solid #f3cac4;padding:14px 18px;border-radius:6px;margin:16px 0;color:#a43b35;font-size:14px;line-height:1.8}.empty-panel{text-align:center;background:#fff;border:1px solid #dce6ef;border-radius:9px;padding:40px 20px;margin-bottom:20px}.empty-symbol{display:inline-grid;place-items:center;width:45px;height:45px;background:#edf5fa;color:#6791aa;border-radius:50%;font-size:25px}.empty-panel h2{font-weight:500;font-size:18px;line-height:1.9}.empty-panel p{font-size:13px;line-height:1.9;color:#718799}.empty-panel>div{display:flex;justify-content:center;align-items:center;gap:20px;margin-top:22px}.empty-panel a{color:#0075b7;font-size:13px}.loading-message{color:#718799;text-align:center;padding:40px}.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}.chapter-bank :is(a,button,input):focus-visible{outline:3px solid #0075b7;outline-offset:3px}@keyframes note-arrive{from{opacity:0;transform:translateY(9px) rotate(-.5deg)}to{opacity:1;transform:translateY(0) rotate(.4deg)}}
@media(max-width:1150px){.question-layout.with-note{grid-template-columns:minmax(0,1fr) 280px;gap:18px}.question-paper{padding:27px}.chapter-grid{gap:14px}.chapter-main-link{padding:16px 18px 0}.marked-entry{padding:9px 18px}}
@media(max-width:950px){.chapter-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.question-layout.with-note{grid-template-columns:minmax(0,1fr)}.correction-note{margin-top:8px}.option-result{font-size:10px}}
@media(max-width:600px){.bank-heading{align-items:flex-start;flex-direction:column;gap:10px;margin-bottom:14px}.bank-heading h1{font-size:23px}.eyebrow{font-size:10px;letter-spacing:1px}.section-heading{align-items:flex-start;flex-direction:column;gap:5px}.section-heading>span{font-size:12px}.chapter-grid{grid-template-columns:1fr;gap:12px}.chapter-card h3{min-height:0}.practice-heading{font-size:12px;flex-wrap:wrap;gap:10px}.question-paper{padding:21px 17px}.question-stem{font-size:17px;line-height:1.9;margin:22px 0}.question-id{display:none}.answer-option{padding:13px 12px;gap:10px;font-size:14px;flex-wrap:wrap}.option-result{margin-left:25px}.blank-answer{gap:10px;flex-wrap:wrap}.blank-answer input{width:calc(100% - 70px)}.blank-result{margin-left:64px}.practice-nav{bottom:5px;gap:8px;padding:12px 9px}.practice-nav button{padding:10px 12px;font-size:12px}.bookmark-button{padding:10px 7px!important}.answer-feedback{padding:15px}.answer-feedback p{font-size:12px}.correction-note{padding:26px 22px}.bank-error{align-items:flex-start;flex-direction:column}.empty-panel>div{flex-wrap:wrap}}
@media(prefers-reduced-motion:reduce){.correction-note{animation:none;transform:none}.chapter-card{transition:none}}

.is-practicing{max-width:960px}.correct-answer{margin-top:25px;padding-top:20px;border-top:1px solid #e9eff4;color:#237449}.correct-answer>span{font-size:12px}.correct-answer p{font-size:17px;line-height:1.9;white-space:pre-wrap;margin:8px 0 0}.analysis-area{margin-top:22px}.analysis-toggle{border:0;background:transparent;color:#0075b7;padding:6px 0}.analysis-content{margin-top:12px;font-size:14px;line-height:1.9;color:#506b80;white-space:pre-wrap;overflow-wrap:anywhere}.single-blank input{flex:1;width:100%}.single-blank .blank-result{margin-left:0}

.question-figures{display:grid;gap:12px;margin-top:18px}.question-figures a{display:block;border:1px solid #e5edf4;border-radius:6px;overflow:hidden;background:#fff;cursor:zoom-in}.question-figures img{display:block;width:100%;height:auto}.question-figures+.question-stem{margin-top:18px}
</style>

