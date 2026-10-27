<template>
  <section class="review-page" v-loading="loading">
    <header class="review-heading"><div><h1>学生作答记录</h1><p>先选择学生，再查看该生的作答并进入批改。</p></div><button @click="load">刷新学生名单</button></header>
    <div class="filters"><label>理论专题 <select v-model="topic" @change="changeTopic"><option value="all">全部六专题</option><option v-for="item in topics" :key="item.id" :value="String(item.id)">{{ item.title }}</option></select></label><input v-model.trim="search" aria-label="查找学生" placeholder="按姓名、学号、用户名或班级查找"></div>
    <p v-if="notice" role="alert" class="notice">{{ notice }}</p>
    <el-table :data="pageView.items" border empty-text="null">
      <el-table-column label="学生姓名"><template #default="{row}">{{ row.student_name || 'null' }}</template></el-table-column>
      <el-table-column label="学号"><template #default="{row}">{{ row.student_number || 'null' }}</template></el-table-column>
      <el-table-column label="班级"><template #default="{row}">{{ row.class_name || 'null' }}</template></el-table-column>
      <el-table-column prop="username" label="用户名"/>
      <el-table-column prop="attempt_count" label="提交份数" width="100"/>
      <el-table-column prop="pending_count" label="待批阅" width="100"/>
      <el-table-column label="操作" width="150"><template #default="{row}"><button :disabled="!row.attempt_count" @click="openStudent(row.id)">{{ row.attempt_count?'查看作答 →':'未提交' }}</button></template></el-table-column>
    </el-table>
    <ListPager :page="pageView.page" :total="pageView.total" @change="changePage"/>
  </section>
</template>
<script setup>
import { computed,onMounted,ref,watch } from 'vue'
import { useRoute,useRouter } from 'vue-router'
import ListPager from '@/components/ListPager.vue'
import { paginate,pageNumber } from '@/domain/pagination'
import { getReviewStudents,getLabQuestions } from '@/api/labTopics'
const route=useRoute(),router=useRouter(),students=ref([]),questions=ref([]),topic=ref('all'),search=ref(''),loading=ref(false),notice=ref('')
const topics=computed(()=>[...new Map(questions.value.map(q=>[q.topic,q.topic_info])).values()].sort((a,b)=>a.id-b.id))
const filtered=computed(()=>students.value.filter(s=>[s.student_name,s.student_number,s.class_name,s.username].some(v=>String(v??'').includes(search.value))))
const page=ref(pageNumber(route.query.page))
const pageView=computed(()=>paginate(filtered.value,page.value))
function changePage(value){page.value=value;router.push({path:route.path,query:{...route.query,page:String(value)}})}
watch(()=>route.query.page,value=>{page.value=pageNumber(value)})
watch(search,()=>{page.value=1})
let request=0
async function load(){
  const current=++request;page.value=pageNumber(route.query.page)
  topic.value=/^[1-6]$/.test(String(route.query.topic))?String(route.query.topic):'all'
  loading.value=true;notice.value='';students.value=[]
  try{if(!questions.value.length)questions.value=await getLabQuestions();const rows=await getReviewStudents(topic.value==='all'?undefined:Number(topic.value));if(current===request)students.value=rows}
  catch{if(current===request)notice.value='学生名单加载失败，请重试。'}
  finally{if(current===request)loading.value=false}
}
function changeTopic(){router.replace({path:'/teacher/questions',query:topic.value==='all'?{}:{topic:topic.value}})}
function openStudent(id){router.push({path:'/teacher/questions/students/'+id,query:{...(topic.value==='all'?{}:{topic:topic.value}),studentsPage:String(pageView.value.page)}})}
watch(()=>route.query.topic,load)
onMounted(load)
</script>

<style scoped>
.review-page{max-width:1400px;margin:auto;color:#19334d}.review-heading{display:flex;justify-content:space-between;align-items:center;gap:20px;margin-bottom:24px}.review-heading h1{margin:10px 0}.review-heading p{color:#586f82;line-height:1.8}.review-page a{color:#0075b7;text-decoration:none}.filters{display:flex;gap:16px;align-items:center;flex-wrap:wrap;margin-bottom:20px}.filters input,.filters select,.review-page textarea,.review-page input[type=number]{padding:10px;border:1px solid #cddfe9;border-radius:5px;background:white;color:#19334d;font:inherit}.filters input{min-width:230px}.review-page button{padding:9px 16px;border:1px solid #b6d7eb;border-radius:5px;background:#0075b7;color:white;cursor:pointer;font:inherit}.review-page button:disabled{opacity:.5;cursor:default}.notice{background:#fff0e6;padding:14px;color:#995333}.summary{background:#eef6fc;border:1px solid #d2e5f1;border-radius:8px;padding:20px;margin:20px 0;line-height:1.8}.answer-field{background:white;border:1px solid #dce7f0;border-radius:8px;padding:22px;margin:16px 0;line-height:1.9}.answer-text{white-space:pre-wrap;overflow-wrap:anywhere;background:#f6f9fc;padding:15px}.review-page textarea{width:100%;box-sizing:border-box;min-height:120px}.manual-mark{display:flex;align-items:center;gap:10px}.manual-mark input{width:100px}.record-actions{margin:20px 0}.review-page table{width:100%}.muted{color:#586f82}@media(max-width:650px){.review-heading{align-items:flex-start;flex-direction:column}.filters{align-items:stretch;flex-direction:column}}
</style>
