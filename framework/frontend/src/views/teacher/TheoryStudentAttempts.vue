<template>
  <section class="review-page" v-loading="loading">
    <router-link :to="backPath">← 返回学生名单</router-link>
    <header class="review-heading"><div><h1>{{ student?.student_name || student?.username || 'null' }}的作答列表</h1><p>学号：{{ student?.student_number || 'null' }} · 班级：{{ student?.class_name || 'null' }}</p></div><button @click="load">刷新作答列表</button></header>
    <p v-if="notice" role="alert" class="notice">{{ notice }}</p>
    <el-table :data="pageView.items" border empty-text="null">
      <el-table-column prop="question_title" label="作答题目"/>
      <el-table-column label="专题" width="90"><template #default="{row}">{{ row.topic }}</template></el-table-column>
      <el-table-column label="提交时间"><template #default="{row}">{{ timeText(row.created_at) }}</template></el-table-column>
      <el-table-column label="状态" width="110"><template #default="{row}">{{ row.status==='graded'?'已批阅':'待批阅' }}</template></el-table-column>
      <el-table-column label="操作" width="150"><template #default="{row}"><button @click="router.push({path:'/teacher/questions/attempts/'+row.id,query:route.query})">{{ row.status==='graded'?'查看批阅':'进入批改' }} →</button></template></el-table-column>
    </el-table>
    <ListPager :page="pageView.page" :total="pageView.total" @change="changePage"/>
  </section>
</template>
<script setup>
import { computed,onMounted,ref,watch } from 'vue'
import { useRoute,useRouter } from 'vue-router'
import ListPager from '@/components/ListPager.vue'
import { paginate,pageNumber } from '@/domain/pagination'
import { getReviewStudentAttempts } from '@/api/labTopics'
const route=useRoute(),router=useRouter(),student=ref(null),attempts=ref([]),loading=ref(false),notice=ref('')
const page=ref(pageNumber(route.query.page))
const pageView=computed(()=>paginate(attempts.value,page.value))
const backPath=computed(()=>({path:'/teacher/questions',query:{...(/^[1-6]$/.test(String(route.query.topic))?{topic:String(route.query.topic)}:{}),page:String(pageNumber(route.query.studentsPage))}}))
function changePage(value){page.value=value;router.push({path:route.path,query:{...route.query,page:String(value)}})}
watch(()=>route.query.page,value=>{page.value=pageNumber(value)})
let request=0
function timeText(value){return new Date(/[Zz]|[+-]\d\d:\d\d$/.test(value)?value:value+'Z').toLocaleString('zh-CN',{timeZone:'Asia/Shanghai'})}
async function load(){
  const current=++request;page.value=pageNumber(route.query.page);loading.value=true;notice.value='';student.value=null;attempts.value=[]
  try{const result=await getReviewStudentAttempts(route.params.studentId,/^[1-6]$/.test(String(route.query.topic))?Number(route.query.topic):undefined);if(current===request){student.value=result.student;attempts.value=result.attempts}}
  catch(e){if(current===request)notice.value=typeof e.response?.data?.detail==='string'?e.response.data.detail:'学生作答列表加载失败。'}
  finally{if(current===request)loading.value=false}
}
watch(()=>[route.params.studentId,route.query.topic],load)
onMounted(load)
</script>

<style scoped>
.review-page{max-width:1400px;margin:auto;color:#19334d}.review-heading{display:flex;justify-content:space-between;align-items:center;gap:20px;margin-bottom:24px}.review-heading h1{margin:10px 0}.review-heading p{color:#586f82;line-height:1.8}.review-page a{color:#0075b7;text-decoration:none}.filters{display:flex;gap:16px;align-items:center;flex-wrap:wrap;margin-bottom:20px}.filters input,.filters select,.review-page textarea,.review-page input[type=number]{padding:10px;border:1px solid #cddfe9;border-radius:5px;background:white;color:#19334d;font:inherit}.filters input{min-width:230px}.review-page button{padding:9px 16px;border:1px solid #b6d7eb;border-radius:5px;background:#0075b7;color:white;cursor:pointer;font:inherit}.review-page button:disabled{opacity:.5;cursor:default}.notice{background:#fff0e6;padding:14px;color:#995333}.summary{background:#eef6fc;border:1px solid #d2e5f1;border-radius:8px;padding:20px;margin:20px 0;line-height:1.8}.answer-field{background:white;border:1px solid #dce7f0;border-radius:8px;padding:22px;margin:16px 0;line-height:1.9}.answer-text{white-space:pre-wrap;overflow-wrap:anywhere;background:#f6f9fc;padding:15px}.review-page textarea{width:100%;box-sizing:border-box;min-height:120px}.manual-mark{display:flex;align-items:center;gap:10px}.manual-mark input{width:100px}.record-actions{margin:20px 0}.review-page table{width:100%}.muted{color:#586f82}@media(max-width:650px){.review-heading{align-items:flex-start;flex-direction:column}.filters{align-items:stretch;flex-direction:column}}
</style>
