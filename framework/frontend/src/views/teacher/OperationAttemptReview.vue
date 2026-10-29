<template>
  <section class="op-page" :aria-busy="loading">
    <header class="op-heading"><div><router-link :to="back">返回操作批改</router-link><h1>{{ attempt?.question.title || '操作作答批改' }}</h1></div><div class="op-actions-group"><el-button :loading="loading" @click="reload">刷新</el-button><el-button v-if="attempt" @click="download">下载日志</el-button></div></header>
    <el-alert v-if="notice" :title="notice" type="error" :closable="false" role="alert" />
    <template v-if="attempt"><div class="op-panel"><p>{{ attempt.identity.class_name ?? 'null' }} · {{ attempt.identity.student_id ?? 'null' }} · {{ attempt.identity.real_name ?? 'null' }}</p><p>题目版本 v{{ attempt.question.number }} · 提交时间 {{ learningDate(attempt.submitted_at) }}（北京时间）</p><p class="op-preserve">{{ attempt.question.prompt }}</p></div>
      <div class="op-panel"><LearningResult :attempt="attempt" :explaining="explaining" @explain="explain" /></div>
      <form class="op-panel review-form" @submit.prevent="save"><label for="operation-review-comment">教师评语</label><textarea id="operation-review-comment" v-model="comment" name="operation-review-comment" autocomplete="off" maxlength="6000" rows="5"></textarea><label class="review-check"><input v-model="confirmed" type="checkbox" name="operation-review-confirmed">确认已查看</label><div><el-button type="primary" native-type="submit" :loading="saving">保存评阅</el-button><span v-if="saved" role="status"> 已保存</span></div></form>
    </template>
  </section>
</template>
<script setup>
import { computed, ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, onBeforeRouteLeave, onBeforeRouteUpdate } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import LearningResult from '@/features/operationQuestions/LearningResult.vue'
import { getLearning, reviewLearning, explainLearning, downloadLearning } from '@/api/operationLearning'
import { learningError, learningDate } from '@/domain/operationLearning'
import '@/features/operationQuestions/operation.css'
import '@/features/operationQuestions/learning.css'
const route = useRoute()
const attempt = ref(null), loading = ref(false), saving = ref(false), explaining = ref(false), saved = ref(false), notice = ref('')
const comment = ref(''), confirmed = ref(false)
const dirty = computed(() => !!attempt.value && (comment.value !== (attempt.value.review.comment || '') || confirmed.value !== attempt.value.review.confirmed))
const back = computed(() => /^\/operations\/reviews(?:\?|$)/.test(String(route.query.back || '')) ? route.query.back : '/operations/reviews')
let request = 0
function accept(data) { attempt.value = data; comment.value = data.review.comment || ''; confirmed.value = data.review.confirmed }
async function load() { const token = ++request; loading.value = true; notice.value = ''; saved.value = false; try { const data = await getLearning(route.params.attemptId); if (token === request) accept(data) } catch (e) { if (token === request) notice.value = learningError(e) } finally { if (token === request) loading.value = false } }
async function allowDiscard() { if (!dirty.value) return true; try { await ElMessageBox.confirm('当前评语尚未保存，是否放弃修改？', '未保存评阅', {confirmButtonText:'放弃修改',cancelButtonText:'继续编辑'}); return true } catch { return false } }
async function reload() { if (saving.value || !await allowDiscard()) return; await load() }
async function save() { if (saving.value) return; saving.value = true; saved.value = false; notice.value = ''; try { accept(await reviewLearning(attempt.value.session_id, {revision:attempt.value.review.revision,comment:comment.value,confirmed:confirmed.value})); saved.value = true } catch (e) { notice.value = learningError(e) } finally { saving.value = false } }
async function explain() { if (explaining.value) return; explaining.value = true; const sid = attempt.value.session_id; try { const data = await explainLearning(sid); if (attempt.value?.session_id === sid) attempt.value = {...attempt.value, ai_text:data.ai_text, ai_status:data.ai_status} } catch (e) { notice.value = learningError(e) } finally { explaining.value = false } }
async function download() { try { await downloadLearning(attempt.value.session_id) } catch (e) { notice.value = learningError(e) } }
onBeforeRouteLeave(async () => !saving.value && await allowDiscard())
onBeforeRouteUpdate(async () => !saving.value && await allowDiscard())
function beforeUnload(event) { if (dirty.value || saving.value) { event.preventDefault(); event.returnValue = '' } }
onMounted(() => window.addEventListener('beforeunload', beforeUnload))
onBeforeUnmount(() => { request++; window.removeEventListener('beforeunload', beforeUnload) })
watch(() => route.params.attemptId, load, {immediate:true})
</script>
