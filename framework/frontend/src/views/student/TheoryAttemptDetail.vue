<template>
  <section class="answer-page" v-loading="loading">
    <header class="answer-header"><div><router-link :to="backPath">返回</router-link><h1>提交内容与反馈</h1></div><button @click="load">刷新评阅状态</button></header>
    <p v-if="notice" class="notice" role="alert">{{ notice }}</p>
    <template v-if="attempt">
      <article class="record"><h2><Notation :text="attempt.question_title"/></h2><p class="muted">{{ timeText(attempt.created_at) }} · {{ attempt.result.status==='graded'?'已评阅':'待教师评阅' }}</p><p>客观项 {{ attempt.result.automatic_score }}/{{ attempt.result.automatic_max }}<span v-if="attempt.result.total_score!==null"> · 总分 {{ attempt.result.total_score }}/{{ attempt.result.total_max }}</span><span v-else> · 论述未计分</span></p></article>
      <article v-for="field in attempt.result.feedback" :key="field.id" class="record">
        <h2><Notation :text="field.label"/></h2><strong>提交内容</strong><p class="answer-text"><Notation :text="answerText(attempt.answers[field.id])"/></p>
        <template v-if="field.status!=='pending_review'"><p>{{ field.status==='correct'?'核对正确':field.status==='partial'?'部分得分':'需调整' }} · {{ field.points }}/{{ field.max_points }} 分</p><p v-for="error in field.errors" :key="error"><Notation :text="error"/></p><p>参考填写：<Notation :text="answerText(field.expected)" :runs="field.expected_runs"/></p><p class="explanation"><Notation :text="field.explanation"/></p></template>
        <template v-else><p>论述由教师评阅。</p><p v-if="field.explanation" class="explanation"><Notation :text="field.explanation"/></p></template>
        <p v-if="attempt.review?.field_comments?.[field.id]">本栏反馈：{{ attempt.review.field_comments[field.id] }}</p>
        <p v-if="attempt.review?.scores?.[field.id]!==undefined">教师评分：{{ attempt.review.scores[field.id] }}/{{ field.max_points }}</p>
      </article>
      <p v-if="attempt.review" class="review-comment">教师评语：{{ attempt.review.comment }}</p>
    </template>
  </section>
</template>
<script setup>
import { computed,onMounted,ref,watch } from 'vue'
import { useRoute } from 'vue-router'
import Notation from '@/components/RailwayNotation.vue'
import { getLabAttempt } from '@/api/labTopics'
import { THEORY_ROOT } from '@/domain/theoryNavigation'
import { pageNumber } from '@/domain/pagination'
const route=useRoute(),attempt=ref(null),loading=ref(false),notice=ref('')
const backPath=computed(()=>{const id=Number(attempt.value?.topic??route.query.topic);return {path:THEORY_ROOT+'/attempts',query:{topic:String(Number.isInteger(id)&&id>=1&&id<=6?id:1),page:String(pageNumber(route.query.page))}}})
let request=0
function answerText(value){return Array.isArray(value)?value.join(' → '):String(value??'null')}
function timeText(value){return new Date(/[Zz]|[+-]\d\d:\d\d$/.test(value)?value:value+'Z').toLocaleString('zh-CN',{timeZone:'Asia/Shanghai'})}
async function load(){
  const current=++request;loading.value=true;notice.value='';attempt.value=null
  try{const result=await getLabAttempt(route.params.attemptId);if(current===request)attempt.value=result}
  catch(e){if(current===request)notice.value=typeof e.response?.data?.detail==='string'?e.response.data.detail:'作答详情加载失败，请重试。'}
  finally{if(current===request)loading.value=false}
}
watch(()=>route.params.attemptId,load)
onMounted(load)
</script>

<style scoped>
.answer-page{width:100%;max-width:1400px;margin:auto;color:#19334d}.answer-header{display:flex;align-items:center;justify-content:space-between;gap:20px;margin-bottom:24px}.answer-header h1{margin:10px 0}.answer-page a{color:#0075b7}.answer-page button,.answer-page select{padding:10px 14px;border:1px solid #c1d7e4;border-radius:6px;background:white;color:#215e84;font:inherit}.answer-page button{cursor:pointer}.filters{display:flex;gap:16px;flex-wrap:wrap;align-items:center;margin-bottom:20px}.record{background:white;border:1px solid #dce7f0;border-radius:8px;padding:22px;margin:16px 0;line-height:1.9}.record header{display:flex;align-items:center;justify-content:space-between;gap:18px}.record header span,.muted{color:#586f82}.record h2{font-size:20px}.record-link{display:inline-block;margin-top:10px}.notice{background:#fff0e6;padding:14px;color:#995333}.answer-text,.explanation{white-space:pre-wrap;overflow-wrap:anywhere}.answer-text{background:#f6f9fc;padding:14px}.review-comment{padding:18px;background:#edf6fb;border-radius:6px}.record p{overflow-wrap:anywhere}@media(max-width:650px){.answer-header,.record header{align-items:flex-start;flex-direction:column}}
</style>
