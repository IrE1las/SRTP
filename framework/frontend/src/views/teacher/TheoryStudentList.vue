<template>
  <section class="op-page" v-loading="loading">
    <header class="op-heading"><div><h1>理论学习</h1><p class="op-muted">按班级查找学生，查看理论作答并进入批改。</p></div></header>
    <div class="op-panel">
      <form class="roster-toolbar" role="search" @submit.prevent="applyFilters">
        <div class="roster-field"><label for="roster-class">班级</label><el-select id="roster-class" v-model="className" filterable clearable placeholder="全部班级" aria-label="选择学生班级" @change="applyFilters"><el-option v-for="name in classes" :key="name" :label="name" :value="name" /></el-select></div>
        <div class="roster-field roster-number"><label for="roster-number">学号</label><el-input id="roster-number" v-model.trim="search" name="student-number" clearable maxlength="100" autocomplete="off" placeholder="输入学号搜索…" @input="page = 1" @clear="applyFilters" /></div>
        <el-button native-type="submit">搜索</el-button>
        <div class="roster-field roster-topic"><label for="roster-topic">理论专题</label><el-select id="roster-topic" v-model="topic" aria-label="理论专题" @change="changeTopic"><el-option label="全部六专题" value="all" /><el-option v-for="item in topics" :key="item.id" :label="item.title" :value="String(item.id)" /></el-select></div>
        <el-button class="roster-refresh" :loading="loading" @click="load">刷新名单</el-button>
      </form>
      <el-alert v-if="notice" :title="notice" type="error" show-icon :closable="false" role="alert" />
      <el-table :data="pageView.items" empty-text="暂无符合条件的学生">
        <el-table-column label="学生姓名" min-width="130"><template #default="{row}">{{ row.student_name || '未填写' }}</template></el-table-column>
        <el-table-column label="学号" min-width="150"><template #default="{row}">{{ row.student_number || '未填写' }}</template></el-table-column>
        <el-table-column label="班级" min-width="140"><template #default="{row}">{{ row.class_name || '未填写' }}</template></el-table-column>
        <el-table-column prop="username" label="用户名" min-width="130" />
        <el-table-column prop="attempt_count" label="提交份数" width="100" />
        <el-table-column prop="pending_count" label="待批阅" width="100" />
        <el-table-column label="操作" width="150"><template #default="{row}"><el-button link type="primary" :disabled="!row.attempt_count" @click="openStudent(row.id)">{{ row.attempt_count ? '查看作答 →' : '未提交' }}</el-button></template></el-table-column>
      </el-table>
      <ListPager :page="pageView.page" :total="pageView.total" @change="changePage" />
    </div>
  </section>
</template>
<script setup>
import { computed,onMounted,ref,watch } from 'vue'
import { useRoute,useRouter } from 'vue-router'
import ListPager from '@/components/ListPager.vue'
import '@/features/operationQuestions/operation.css'
import { paginate,pageNumber } from '@/domain/pagination'
import { getReviewStudents,getLabQuestions } from '@/api/labTopics'
const route=useRoute(),router=useRouter(),students=ref([]),questions=ref([]),topic=ref('all'),className=ref(''),search=ref(''),loading=ref(false),notice=ref('')
const topics=computed(()=>[...new Map(questions.value.map(q=>[q.topic,q.topic_info])).values()].sort((a,b)=>a.id-b.id))
const classes=computed(()=>[...new Set(students.value.map(student=>student.class_name).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'zh-CN',{numeric:true})))
const filtered=computed(()=>students.value.filter(student=>(!className.value || student.class_name===className.value) && String(student.student_number || '').includes(search.value)).sort((a,b)=>String(a.class_name || '').localeCompare(String(b.class_name || ''),'zh-CN',{numeric:true}) || String(a.student_number || '').localeCompare(String(b.student_number || ''),'zh-CN',{numeric:true}) || a.id-b.id))
const page=ref(pageNumber(route.query.page))
const pageView=computed(()=>paginate(filtered.value,page.value))
function filterQuery(){return {...(topic.value==='all'?{}:{topic:topic.value}),...(className.value?{class:className.value}:{}),...(search.value?{search:search.value}:{})}}
function applyFilters(){page.value=1;router.push({path:'/teacher/questions',query:filterQuery()})}
function changePage(value){page.value=value;router.push({path:'/teacher/questions',query:{...filterQuery(),page:String(value)}})}
watch(()=>route.query,()=>{page.value=pageNumber(route.query.page);className.value=String(route.query.class || '');search.value=String(route.query.search || '')})
let request=0
async function load(){
  const current=++request;page.value=pageNumber(route.query.page)
  topic.value=/^[1-6]$/.test(String(route.query.topic))?String(route.query.topic):'all'
  className.value=String(route.query.class || '');search.value=String(route.query.search || '')
  loading.value=true;notice.value='';students.value=[]
  try{if(!questions.value.length)questions.value=await getLabQuestions();const rows=await getReviewStudents(topic.value==='all'?undefined:Number(topic.value));if(current===request)students.value=rows}
  catch{if(current===request)notice.value='学生名单加载失败，请重试。'}
  finally{if(current===request)loading.value=false}
}
function changeTopic(){router.push({path:'/teacher/questions',query:filterQuery()})}
function openStudent(id){router.push({path:'/teacher/questions/students/'+id,query:{...filterQuery(),studentsPage:String(pageView.value.page)}})}
watch(()=>route.query.topic,load)
onMounted(load)
</script>
<style scoped>
.roster-toolbar{display:flex;align-items:flex-end;gap:14px;flex-wrap:wrap;margin-bottom:24px}.roster-field{display:grid;gap:7px;width:175px}.roster-field label{font-size:14px;color:#40596f}.roster-number{width:230px}.roster-topic{width:190px;margin-left:auto}.roster-toolbar .roster-refresh{min-height:36px;padding:7px 11px;font-size:14px;margin-bottom:4px}.roster-toolbar>.el-button{margin-bottom:0}@media(max-width:1100px){.roster-topic{margin-left:0}}@media(max-width:650px){.roster-field,.roster-number,.roster-topic{width:100%}}@media(pointer:coarse){.roster-toolbar .roster-refresh{min-height:44px;margin-bottom:0}}
</style>
