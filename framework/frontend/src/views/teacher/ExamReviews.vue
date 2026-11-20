<template>
  <section class="op-page exam-page" v-loading="loading">
    <header class="exam-masthead"><div><h1>考试批阅</h1><p>查看操作题与客观题答卷，核对判分结果，填写并发布成绩。</p></div><div class="exam-tools"><router-link to="/exams/manage">考试管理</router-link><el-button @click="load">刷新答卷</el-button></div></header>
    <div class="review-counts"><span>已交卷 <strong>{{ counts.all }}</strong></span><span>待发布成绩 <strong>{{ counts.pending }}</strong></span><span>已发布成绩 <strong>{{ counts.published }}</strong></span></div>
    <form class="exam-review-filters" @submit.prevent="apply"><el-select v-model="filters.status" aria-label="批阅状态" @change="apply"><el-option label="待发布成绩" value="pending"/><el-option label="已发布成绩" value="published"/><el-option label="全部答卷" value="all"/></el-select><el-input v-model="filters.search" aria-label="搜索答卷" placeholder="考试名称、姓名、学号或班级" maxlength="150" clearable @clear="apply"/><el-button native-type="submit">查询</el-button><router-link v-if="filters.exam_id" to="/exams/grading">查看全部考试</router-link></form>
    <el-alert v-if="notice" :title="notice" type="error" :closable="false" role="alert"/>
    <section class="exam-list-panel"><el-table :data="items" empty-text="暂无符合条件的已交卷答卷。">
      <el-table-column label="考试 / 学生" min-width="240"><template #default="{row}"><router-link class="exam-row-title" :to="`/exams/manage/attempts/${row.session_id}?from=grading`">{{ row.name }}</router-link><p class="exam-time">{{ row.identity.real_name || '未填姓名' }} · {{ row.identity.student_id || '未填学号' }}<br>{{ row.identity.class_name || '未填班级' }}</p></template></el-table-column>
      <el-table-column label="交卷时间" min-width="190"><template #default="{row}">{{ beijingTime(row.submitted_at) }}<p class="exam-time">{{ row.finish_reason_text }}</p></template></el-table-column>
      <el-table-column label="类型" width="100"><template #default="{row}">{{ row.kind === 'objective' ? '客观题' : '操作题' }}</template></el-table-column>
      <el-table-column label="批阅状态" width="140"><template #default="{row}"><el-tag :type="row.grade.status==='published'?'success':'warning'">{{ gradeLabels[row.grade.status] || '待批阅' }}</el-tag></template></el-table-column>
      <el-table-column label="成绩" width="110"><template #default="{row}">{{ row.grade.score ?? '—' }}</template></el-table-column>
      <el-table-column label="批阅" width="130"><template #default="{row}"><router-link :to="`/exams/manage/attempts/${row.session_id}?from=grading`">{{ row.grade.status==='published'?'查看 / 修订':'进入批阅' }}</router-link></template></el-table-column>
    </el-table><ListPager :page="page" :total="total" @change="changePage"/></section>
  </section>
</template>
<script setup>
import '@/features/exams/exam.css'
import { onBeforeUnmount, ref, reactive, watch } from 'vue'
import { useRoute } from 'vue-router'
import ListPager from '@/components/ListPager.vue'
import { examReviews } from '@/api/exams'
import { beijingTime, examError } from '@/domain/exams'
const route=useRoute(),loading=ref(false),notice=ref(''),items=ref([]),total=ref(0),page=ref(1)
const filters=reactive({status:'pending',search:'',exam_id:undefined}),counts=reactive({all:0,pending:0,published:0})
const gradeLabels={ungraded:'待批阅',draft:'成绩草稿',confirmed:'已确认待发布',published:'已发布'}
let serial=0
async function load(){const ticket=++serial;loading.value=true;notice.value='';try{const data=await examReviews({...filters,page:page.value});if(ticket!==serial)return;items.value=data.items;total.value=data.total;Object.assign(counts,data.counts);if(!items.value.length&&page.value>1){page.value=Math.max(1,Math.ceil(total.value/6));await load()}}catch(e){if(ticket===serial)notice.value=examError(e)}finally{if(ticket===serial)loading.value=false}}
function apply(){page.value=1;load()}
function changePage(value){page.value=value;load()}
watch(()=>route.query.exam_id, value=>{filters.exam_id=/^[1-9]\d*$/.test(String(value||''))?Number(value):undefined;page.value=1;load()},{immediate:true})
onBeforeUnmount(()=>{serial++})
</script>
<style scoped>
.review-counts{display:flex;flex-wrap:wrap;gap:20px 35px;padding:20px 24px;background:white;border:1px solid #e0e7ef;border-radius:8px;margin-bottom:22px;color:#586f82}.review-counts strong{margin-left:10px;font-size:24px;color:#19334d}.exam-review-filters{display:flex;gap:12px;align-items:center;margin-bottom:20px}.exam-review-filters>.el-select{width:200px;flex-shrink:0}.exam-review-filters>.el-input{min-width:0;flex:1}.exam-review-filters>a{white-space:nowrap;font-size:14px}@media(max-width:650px){.review-counts{gap:12px;padding:16px;font-size:14px}.review-counts strong{font-size:20px}.exam-review-filters{flex-wrap:wrap}.exam-review-filters>.el-select{width:100%}.exam-review-filters>.el-input{flex-basis:65%}}
</style>
