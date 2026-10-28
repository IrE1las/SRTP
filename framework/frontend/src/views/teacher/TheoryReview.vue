<template>
  <section class="review-page" v-loading="loading">
    <router-link v-if="attempt" :to="{path:'/teacher/questions/students/'+attempt.student.id,query:route.query}">← 返回该生作答列表</router-link>
    <router-link v-else to="/teacher/questions">← 返回学生名单</router-link>
    <p v-if="notice" role="alert" class="notice">{{ notice }}</p>
    <template v-if="attempt">
<<<<<<< Updated upstream
      <header class="review-heading"><div><h1>{{ attempt.review?'查看批阅':'批改作答' }}</h1><p>{{ attempt.student.student_name || attempt.student.username || 'null' }} · 学号 {{ attempt.student.student_number || 'null' }} · {{ attempt.question_title }}</p></div></header>
=======
      <header class="review-heading"><div><h1>{{ attempt.review?'查看批阅':'批改作答' }}</h1><p>{{ attempt.student.student_name || attempt.student.username || 'null' }} · 学号 {{ attempt.student.student_number || 'null' }} · 班级 {{ attempt.student.class_name || 'null' }} · {{ attempt.question_title }}</p><p v-if="attempt.student.source === 'migration_current_identity'">身份为旧库迁移时记录，提交时身份未确认。</p></div></header>
>>>>>>> Stashed changes
      <div class="summary">作答编号 {{ attempt.id }} · 客观项 {{ attempt.result.automatic_score }}/{{ attempt.result.automatic_max }}<span v-if="attempt.review"> · 总分 {{ attempt.result.total_score }}/{{ attempt.result.total_max }}</span><span v-else> · 论述待人工评分</span></div>
      <article v-for="field in attempt.result.feedback" :key="field.id" class="answer-field">
        <h3><Notation :text="field.label"/></h3><strong>学生作答</strong><p class="answer-text"><Notation :text="answerText(attempt.answers[field.id])"/></p>
        <template v-if="field.status==='pending_review'">
          <p class="muted">评分要点</p><ul><li v-for="criterion in field.criteria" :key="criterion">{{ criterion }}</li></ul>
          <p v-if="field.explanation" class="answer-text"><Notation :text="field.explanation"/></p>
          <label class="manual-mark">本栏评分 <input v-model.number="scores[field.id]" type="number" min="0" :max="field.max_points" step="1" :disabled="!!attempt.review||saving"> / {{ field.max_points }}</label>
        </template>
        <template v-else><p>客观核对：{{ field.status==='correct'?'正确':field.status==='partial'?'部分得分':'需调整' }} · {{ field.points }}/{{ field.max_points }}</p><p>参考填写：<Notation :text="answerText(field.expected)" :runs="field.expected_runs"/></p><p class="answer-text"><Notation :text="field.explanation"/></p></template>
      </article>
      <label>教师评语<textarea v-model="comment" maxlength="6000" :disabled="!!attempt.review||saving" placeholder="填写本次作答的评语"></textarea></label>
      <div class="record-actions"><button v-if="!attempt.review" @click="save" :disabled="saving">{{ saving?'保存中…':'保存评阅' }}</button><p v-else>已保存评阅。</p></div>
    </template>
  </section>
</template>
<script setup>
import { onMounted,ref,watch } from 'vue'
import { useRoute } from 'vue-router'
import Notation from '@/components/RailwayNotation.vue'
import { getReviewAttempt,reviewLabAttempt } from '@/api/labTopics'
const route=useRoute(),attempt=ref(null),scores=ref({}),comment=ref(''),loading=ref(false),saving=ref(false),notice=ref('')
let request=0
function answerText(value){return Array.isArray(value)?value.join(' → '):String(value??'null')}
async function load(){
  const current=++request;loading.value=true;notice.value='';attempt.value=null;scores.value={};comment.value=''
  try{const result=await getReviewAttempt(route.params.attemptId);if(current!==request)return;attempt.value=result;scores.value=result.review?.scores?{...result.review.scores}:Object.fromEntries(result.rubric.map(f=>[f.id,'']));comment.value=result.review?.comment||''}
  catch(e){if(current===request)notice.value=typeof e.response?.data?.detail==='string'?e.response.data.detail:'作答详情加载失败。'}
  finally{if(current===request)loading.value=false}
}
async function save(){
  if(!attempt.value||attempt.value.review||saving.value)return
  const current=attempt.value
  if(!comment.value.trim()||current.rubric.some(f=>!Number.isInteger(scores.value[f.id])||scores.value[f.id]<0||scores.value[f.id]>f.points)){notice.value='请逐栏填写有效评分及评语。';return}
  saving.value=true;notice.value=''
  try{const result=await reviewLabAttempt(current.id,{scores:{...scores.value},comment:comment.value});if(attempt.value?.id===current.id)Object.assign(attempt.value,result)}
  catch(e){if(attempt.value?.id===current.id)notice.value=typeof e.response?.data?.detail==='string'?e.response.data.detail:'评阅保存失败。'}
  finally{saving.value=false}
}
watch(()=>route.params.attemptId,load)
onMounted(load)
</script>

<style scoped>
.review-page{max-width:1400px;margin:auto;color:#19334d}.review-heading{display:flex;justify-content:space-between;align-items:center;gap:20px;margin-bottom:24px}.review-heading h1{margin:10px 0}.review-heading p{color:#586f82;line-height:1.8}.review-page a{color:#0075b7;text-decoration:none}.filters{display:flex;gap:16px;align-items:center;flex-wrap:wrap;margin-bottom:20px}.filters input,.filters select,.review-page textarea,.review-page input[type=number]{padding:10px;border:1px solid #cddfe9;border-radius:5px;background:white;color:#19334d;font:inherit}.filters input{min-width:230px}.review-page button{padding:9px 16px;border:1px solid #b6d7eb;border-radius:5px;background:#0075b7;color:white;cursor:pointer;font:inherit}.review-page button:disabled{opacity:.5;cursor:default}.notice{background:#fff0e6;padding:14px;color:#995333}.summary{background:#eef6fc;border:1px solid #d2e5f1;border-radius:8px;padding:20px;margin:20px 0;line-height:1.8}.answer-field{background:white;border:1px solid #dce7f0;border-radius:8px;padding:22px;margin:16px 0;line-height:1.9}.answer-text{white-space:pre-wrap;overflow-wrap:anywhere;background:#f6f9fc;padding:15px}.review-page textarea{width:100%;box-sizing:border-box;min-height:120px}.manual-mark{display:flex;align-items:center;gap:10px}.manual-mark input{width:100px}.record-actions{margin:20px 0}.review-page table{width:100%}.muted{color:#586f82}@media(max-width:650px){.review-heading{align-items:flex-start;flex-direction:column}.filters{align-items:stretch;flex-direction:column}}
</style>
