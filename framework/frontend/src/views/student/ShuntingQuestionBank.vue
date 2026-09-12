<template>
  <main class="shunting-question-page">
    <header class="question-heading">
      <div>
        <p class="eyebrow">原图车站 · 调车题库</p>
        <h1>调车进路连锁练习</h1>
        <p class="heading-description">题目直接来自已核对的原始车站连锁表。每题分别检查排列按钮、道岔、敌对信号和轨道区段。</p>
      </div>
      <el-tag v-if="questions.length" effect="plain">{{ questions.length }} 道题</el-tag>
    </header>

    <div v-loading="loading" class="question-layout">
      <aside class="question-list" aria-label="调车进路题目列表">
        <div class="list-heading"><strong>选择进路</strong><span>20—54号</span></div>
        <button v-for="item in questions" :key="item.id" :class="['question-item', { active: item.id === selectedId }]" @click="selectQuestion(item.id)">
          <span class="route-number">{{ item.route_number }}</span>
          <span class="route-copy"><strong>{{ item.direction }}{{ item.route }}</strong><small>{{ difficultyText(item.difficulty) }}</small></span>
          <span aria-hidden="true">›</span>
        </button>
        <el-empty v-if="!loading && !questions.length" description="题库尚未生成，请联系教师" />
      </aside>

      <section v-if="question" class="question-card" aria-live="polite">
        <div class="question-card-heading">
          <div><p class="eyebrow">第 {{ question.route_number }} 号</p><h2>{{ question.title }}</h2></div>
          <el-tag :type="difficultyType(question.difficulty)" effect="light">{{ difficultyText(question.difficulty) }}</el-tag>
        </div>
        <p class="question-prompt">{{ question.prompt }}</p>

        <div class="answer-section">
          <h3>排列进路按钮</h3>
          <el-checkbox-group v-model="answer.route_buttons" class="option-grid">
            <el-checkbox v-for="code in question.options.route_buttons" :key="code" :label="code" border>{{ code }}</el-checkbox>
          </el-checkbox-group>
        </div>

        <div class="answer-section">
          <h3>道岔位置</h3>
          <div class="switch-grid">
            <label v-for="code in question.options.switches" :key="code" class="switch-option">
              <span>{{ code }}号道岔</span>
              <span class="switch-selects"><select :value="answer.switches[code] || ''" :aria-label="`${code}号道岔位置`" @change="setSwitch(code, $event.target.value)">
                <option value="">位置</option><option value="normal">定位</option><option value="reverse">反位</option>
              </select><select :value="answer.switch_roles[code] || ''" :aria-label="`${code}号道岔作用类别`" @change="setSwitchRole(code, $event.target.value)">
                <option value="">类别</option><option v-for="role in question.options.switch_roles" :key="role" :value="role">{{ roleName(role) }}</option>
              </select></span>
            </label>
          </div>
        </div>

        <div class="answer-section">
          <h3>敌对信号</h3>
          <el-checkbox-group v-model="answer.hostile_signals" class="option-grid wide-options">
            <el-checkbox v-for="value in question.options.hostile_signals" :key="value" :label="value" border>{{ value }}</el-checkbox>
          </el-checkbox-group>
        </div>

        <div class="answer-section">
          <h3>轨道区段</h3>
          <el-checkbox-group v-model="answer.track_sections" class="option-grid wide-options">
            <el-checkbox v-for="value in question.options.track_sections" :key="value" :label="value" border>{{ value }}</el-checkbox>
          </el-checkbox-group>
        </div>

        <div class="answer-actions"><el-button @click="resetAnswer">重置本题</el-button><el-button type="primary" :loading="submitting" @click="submit">提交检验</el-button></div>
        <p v-if="notice" class="notice" role="status">{{ notice }}</p>

        <section v-if="result" class="result-card" :class="{ success: result.all_correct }">
          <div class="result-title"><strong>{{ result.all_correct ? '全部正确' : '需要调整' }}</strong><span>{{ Math.round(result.score * 100) }} 分</span></div>
          <p>{{ result.feedback }}</p>
          <div v-if="!result.all_correct" class="error-groups">
            <div v-for="group in errorGroups" :key="group.key" v-show="group.items.length"><strong>{{ group.label }}</strong><span>{{ group.items.join('、') }}</span></div>
          </div>
          <div v-if="result.all_correct" class="category-score"><span v-for="(score, key) in result.details.category_scores" :key="key">{{ categoryLabels[key] }} {{ score.matched }}/{{ score.expected }}</span></div>
        </section>
      </section>
      <el-empty v-else-if="!loading" description="请选择一道进路题目" />
    </div>
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { getShuntingQuestion, listShuntingQuestions, submitShuntingQuestion } from '@/api/shuntingQuestions'

const questions = ref([]), question = ref(null), selectedId = ref(null), loading = ref(false), submitting = ref(false), notice = ref(''), result = ref(null)
const emptyAnswer = () => ({ route_buttons: [], switches: {}, switch_roles: {}, hostile_signals: [], track_sections: [] })
const answer = ref(emptyAnswer())
const categoryLabels = { route_buttons: '按钮', switches: '道岔', hostile_signals: '敌对信号', track_sections: '区段' }
const difficultyText = value => ({ easy: '基础', medium: '进阶', hard: '综合' }[value] || value)
const difficultyType = value => ({ easy: 'success', medium: 'warning', hard: 'danger' }[value] || 'info')

const errorGroups = computed(() => {
  const errors = result.value?.details?.errors || {}
  return [
    { key: 'route_buttons', label: '进路按钮', items: [...(errors.route_buttons?.missing || []).map(item => `漏选 ${item}`), ...(errors.route_buttons?.extra || []).map(item => `多选 ${item}`)] },
    { key: 'switches', label: '道岔位置/类别', items: [...(errors.switches?.missing || []).map(item => `漏选 ${item}`), ...(errors.switches?.extra || []).map(item => `多选 ${item}`), ...(errors.switches?.wrong_position || []).map(item => `${item.switch} 当前${positionName(item.student)}，应为${positionName(item.expected)}`), ...(errors.switches?.missing_role || []).map(item => `漏选类别 ${item}`), ...(errors.switches?.extra_role || []).map(item => `多选类别 ${item}`), ...(errors.switches?.wrong_role || []).map(item => `${item.switch} 类别错误，应为${roleName(item.expected)}`)] },
    { key: 'hostile_signals', label: '敌对信号', items: [...(errors.hostile_signals?.missing || []).map(item => `漏选 ${item}`), ...(errors.hostile_signals?.extra || []).map(item => `多选 ${item}`)] },
    { key: 'track_sections', label: '轨道区段', items: [...(errors.track_sections?.missing || []).map(item => `漏选 ${item}`), ...(errors.track_sections?.extra || []).map(item => `多选 ${item}`)] },
  ]
})
const positionName = value => value === 'normal' ? '定位' : value === 'reverse' ? '反位' : '未选择'
const roleName = value => ({ required: '普通', protective: '防护', driven: '带动' }[value] || value)

function resetAnswer() { answer.value = emptyAnswer(); result.value = null; notice.value = '' }
function setSwitch(code, value) { if (value) answer.value.switches[code] = value; else delete answer.value.switches[code]; result.value = null }
function setSwitchRole(code, value) { if (value) answer.value.switch_roles[code] = value; else delete answer.value.switch_roles[code]; result.value = null }
async function selectQuestion(id) {
  if (id === selectedId.value && question.value) return
  selectedId.value = id; loading.value = true; notice.value = ''; result.value = null
  try { question.value = await getShuntingQuestion(id); resetAnswer() }
  catch (error) { question.value = null; notice.value = `题目加载失败：${error.response?.data?.detail || error.message}` }
  finally { loading.value = false }
}
async function submit() {
  if (!question.value || submitting.value) return
  submitting.value = true; notice.value = ''
  try { result.value = await submitShuntingQuestion(question.value.id, JSON.parse(JSON.stringify(answer.value))) }
  catch (error) { notice.value = `提交失败：${error.response?.data?.detail || error.message}` }
  finally { submitting.value = false }
}
onMounted(async () => {
  loading.value = true
  try { questions.value = await listShuntingQuestions(); if (questions.value.length) await selectQuestion(questions.value[0].id) }
  catch (error) { notice.value = `题库加载失败：${error.response?.data?.detail || error.message}` }
  finally { loading.value = false }
})
</script>

<style scoped>
.shunting-question-page { max-width: 1500px; margin: 0 auto; color: #19334d; }
.question-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; margin-bottom: 22px; }.eyebrow { margin: 0 0 9px; color: #0075b7; font-size: var(--ui-text-sm); letter-spacing: 2px; }.question-heading h1 { margin: 0 0 10px; font-size: 29px; font-weight: 600; }.heading-description { margin: 0; color: #75879a; font-size: var(--ui-text-base); line-height: 1.8; }
.question-layout { display: grid; grid-template-columns: 285px minmax(0, 1fr); align-items: start; gap: 18px; }.question-list, .question-card { background: #fff; border: 1px solid #e2e9f0; border-radius: 9px; }.question-list { overflow: hidden; }.list-heading { display: flex; justify-content: space-between; padding: 17px 18px; border-bottom: 1px solid #edf1f5; color: #557086; font-size: var(--ui-text-base); }.list-heading span { color: #586f82; }.question-item { display: flex; align-items: center; gap: 10px; width: 100%; padding: 12px 14px; border: 0; border-bottom: 1px solid #f0f3f6; background: #fff; color: #50687d; text-align: left; }.question-item:hover, .question-item.active { background: #eef6fb; color: #126f9e; }.route-number { display: grid; place-items: center; width: 34px; height: 30px; border-radius: 5px; background: #f0f5f8; color: #6b8497; font: var(--ui-text-md) Georgia, serif; }.question-item.active .route-number { background: #d8edf8; color: #14739e; }.route-copy { display: flex; flex: 1; min-width: 0; flex-direction: column; gap: 4px; }.route-copy strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: var(--ui-text-base); font-weight: 500; }.route-copy small { color: #586f82; font-size: var(--ui-text-sm); }.question-card { padding: 24px 27px 28px; }.question-card-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 15px; }.question-card-heading h2 { margin: 0; font-size: 23px; font-weight: 600; }.question-prompt { margin: 14px 0 22px; padding: 13px 15px; border-left: 3px solid #67a8c5; border-radius: 3px; background: #f3f8fb; color: #5d7487; font-size: var(--ui-text-base); line-height: 1.9; }.answer-section { margin-top: 22px; padding-top: 18px; border-top: 1px solid #edf1f5; }.answer-section h3 { margin: 0 0 12px; color: #526d81; font-size: var(--ui-text-base); font-weight: 600; }.option-grid { display: flex; flex-wrap: wrap; gap: 9px; }.option-grid :deep(.el-checkbox) { margin: 0; height: auto; }.option-grid :deep(.el-checkbox.is-bordered) { padding: 8px 10px 8px 8px; border-color: #dce7ee; }.option-grid :deep(.el-checkbox__label) { color: #536d80; font-size: var(--ui-text-base); white-space: normal; }.wide-options :deep(.el-checkbox) { max-width: 270px; }.switch-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 10px; }.switch-option { display: flex; align-items: center; justify-content: space-between; gap: 7px; padding: 8px 10px; border: 1px solid #dce7ee; border-radius: 5px; color: #536d80; font-size: var(--ui-text-base); }.switch-selects { display: inline-flex; gap: 4px; }.switch-option select { min-width: 68px; padding: 4px 5px; border: 1px solid #ccdce6; border-radius: 4px; color: #38647b; background: #fbfdfe; }.answer-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 26px; }.notice { margin: 14px 0 0; padding: 10px 12px; border-radius: 5px; background: #fff5e9; color: #a25c2d; font-size: var(--ui-text-base); }.result-card { margin-top: 20px; padding: 17px; border: 1px solid #edcfbf; border-radius: 7px; background: #fff9f4; color: #865538; }.result-card.success { border-color: #c9e6dc; background: #f2fbf7; color: #277a68; }.result-title { display: flex; justify-content: space-between; font-size: var(--ui-text-md); }.result-title span { font: var(--ui-text-lead) Georgia, serif; }.result-card p { margin: 8px 0 0; color: #718796; font-size: var(--ui-text-base); }.error-groups { display: grid; gap: 7px; margin-top: 14px; }.error-groups > div { display: grid; grid-template-columns: 75px minmax(0, 1fr); gap: 8px; padding: 8px 10px; border-radius: 4px; background: #fff; font-size: var(--ui-text-base); line-height: 1.6; }.error-groups strong { color: #966142; }.error-groups span { overflow-wrap: anywhere; color: #6e7f8c; }.category-score { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 12px; color: #5c8a7d; font-size: var(--ui-text-base); }
@media (max-width: 850px) { .question-layout { grid-template-columns: 1fr; }.question-list { max-height: 270px; overflow-y: auto; }.question-card { padding: 20px 17px 22px; } }
</style>
