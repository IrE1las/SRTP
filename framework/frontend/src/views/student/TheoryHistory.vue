<template>
  <section class="answer-page" v-loading="loading">
    <header class="answer-header"><div><router-link :to="THEORY_ROOT">返回</router-link><h1>我的作答</h1></div><router-link :to="theoryTopicPath(topicId)">返回当前专题</router-link></header>
    <div class="filters"><label>筛选专题 <select v-model.number="topicId" @change="changeTopic"><option v-for="topic in topics" :key="topic.id" :value="topic.id">{{ topic.title }}</option></select></label><button @click="load">刷新评阅状态</button></div>
    <p v-if="notice" class="notice" role="alert">{{ notice }}</p>
    <el-empty v-if="!loading&&!attempts.length&&!notice" description="还没有提交专题作答"/>
    <article v-for="attempt in attempts" :key="attempt.id" class="record">
      <header><strong><Notation :text="attempt.question_title"/></strong><span>{{ attempt.result.status==='graded'?'已评阅':'待教师评阅' }}</span></header>
      <small class="muted">{{ timeText(attempt.created_at) }}</small>
      <p>客观项 {{ attempt.result.automatic_score }}/{{ attempt.result.automatic_max }}<span v-if="attempt.result.total_score!==null"> · 总分 {{ attempt.result.total_score }}/{{ attempt.result.total_max }}</span><span v-else> · 论述未计分</span></p>
      <router-link class="record-link" :to="detailPath(attempt.id)">查看提交内容与反馈 →</router-link>
    </article>
    <ListPager v-if="!loading&&!notice" :page="page" :total="total" @change="changePage"/>
  </section>
</template>
<script setup>
import { computed,onMounted,ref,watch } from 'vue'
import { useRoute,useRouter } from 'vue-router'
import Notation from '@/components/RailwayNotation.vue'
import ListPager from '@/components/ListPager.vue'
import { getLabQuestions,getLabAttemptPage } from '@/api/labTopics'
import { THEORY_ROOT,theoryTopicPath } from '@/domain/theoryNavigation'
import { pageNumber } from '@/domain/pagination'
const route=useRoute(),router=useRouter(),attempts=ref([]),questions=ref([]),topicId=ref(1),page=ref(1),total=ref(0),loading=ref(false),notice=ref('')
const topics=computed(()=>[...new Map(questions.value.map(q=>[q.topic,q.topic_info])).values()].sort((a,b)=>a.id-b.id))
let request=0
function timeText(value){return new Date(/[Zz]|[+-]\d\d:\d\d$/.test(value)?value:value+'Z').toLocaleString('zh-CN',{timeZone:'Asia/Shanghai'})}
async function load(){
  const current=++request,id=Number(route.query.topic),requestedPage=pageNumber(route.query.page)
  topicId.value=Number.isInteger(id)&&id>=1&&id<=6?id:1
  loading.value=true;notice.value='';attempts.value=[]
  try{
    if(!questions.value.length)questions.value=await getLabQuestions()
    if(current!==request)return
    const result=await getLabAttemptPage(topicId.value,requestedPage)
    if(current!==request)return
    attempts.value=result.items;page.value=result.page;total.value=result.total
    if(result.page!==requestedPage)await router.replace({path:THEORY_ROOT+'/attempts',query:{topic:String(topicId.value),page:String(result.page)}})
  }catch{if(current===request)notice.value='作答记录加载失败，请重试。'}
  finally{if(current===request)loading.value=false}
}
function changeTopic(){router.push({path:THEORY_ROOT+'/attempts',query:{topic:String(topicId.value),page:'1'}})}
function changePage(value){router.push({path:THEORY_ROOT+'/attempts',query:{topic:String(topicId.value),page:String(value)}})}
function detailPath(id){return {path:THEORY_ROOT+'/attempts/'+id,query:{topic:String(topicId.value),page:String(page.value)}}}
watch(()=>[route.query.topic,route.query.page],load)
onMounted(load)
</script>

<style scoped>
.answer-page{width:100%;max-width:1400px;margin:auto;color:#19334d}.answer-header{display:flex;align-items:center;justify-content:space-between;gap:20px;margin-bottom:24px}.answer-header h1{margin:10px 0}.answer-page a{color:#0075b7}.answer-page button,.answer-page select{padding:10px 14px;border:1px solid #c1d7e4;border-radius:6px;background:white;color:#215e84;font:inherit}.answer-page button{cursor:pointer}.filters{display:flex;gap:16px;flex-wrap:wrap;align-items:center;margin-bottom:20px}.record{background:white;border:1px solid #dce7f0;border-radius:8px;padding:22px;margin:16px 0;line-height:1.9}.record header{display:flex;align-items:center;justify-content:space-between;gap:18px}.record header span,.muted{color:#586f82}.record h2{font-size:20px}.record-link{display:inline-block;margin-top:10px}.notice{background:#fff0e6;padding:14px;color:#995333}.answer-text,.explanation{white-space:pre-wrap;overflow-wrap:anywhere}.answer-text{background:#f6f9fc;padding:14px}.review-comment{padding:18px;background:#edf6fb;border-radius:6px}.record p{overflow-wrap:anywhere}@media(max-width:650px){.answer-header,.record header{align-items:flex-start;flex-direction:column}}
</style>
