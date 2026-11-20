<template>
  <section id="exam-paper" tabindex="-1" class="exam-form-section">
    <div class="exam-section-head"><h2>客观题组卷</h2><strong :class="{invalid:total !== 100}">{{ modelValue.length }} 题 / {{ total }} 分</strong></div>
    <p class="op-help">按试卷顺序选题并设置分值，总分须为100分。每题全对得分，错答、漏选或未答得0分；填空沿用题库核验规则。</p>
    <p v-if="error" role="alert" class="exam-field-error">{{ error }}</p>
    <div class="paper-selection">
      <h3>已选题目</h3>
      <p v-if="!modelValue.length" class="op-muted">从下方题库添加题目。</p>
      <article v-for="(item, index) in modelValue" :key="item.question_id" class="selected-question">
        <div><strong>{{ index + 1 }}. {{ objectiveKinds[known[item.question_id]?.kind] || '客观题' }}</strong><p>{{ known[item.question_id]?.stem || item.question_id }}</p><small v-if="known[item.question_id]?.unavailable" class="invalid">本题已不可用</small></div>
        <div v-if="!published" class="selected-controls"><el-input-number :model-value="item.points" :min="1" :max="100" :precision="0" :disabled="disabled" :aria-label="`第${index + 1}题分值`" @update:model-value="points(index, $event)" /><span>分</span><el-button :disabled="disabled || index === 0" aria-label="上移题目" @click="move(index,-1)">↑</el-button><el-button :disabled="disabled || index === modelValue.length - 1" aria-label="下移题目" @click="move(index,1)">↓</el-button><el-button :disabled="disabled" @click="remove(index)">移除</el-button></div><strong v-else>{{ item.points }} 分</strong>
      </article>
    </div>
    <template v-if="!published">
      <h3>从题库选题</h3><div class="paper-filters"><el-input v-model="filters.search" placeholder="搜索题干或题号" clearable aria-label="搜索客观题" @keydown.enter.prevent="load(1)" /><el-select v-model="filters.chapter" clearable placeholder="全部章节" aria-label="章节" @change="load(1)"><el-option v-for="(name,index) in chapters" :key="name" :label="`${index+1}. ${name}`" :value="index+1" /></el-select><el-select v-model="filters.kind" clearable placeholder="全部题型" aria-label="题型" @change="load(1)"><el-option v-for="(label,key) in objectiveKinds" :key="key" :value="key" :label="label" /></el-select><el-button :disabled="disabled" @click="load(1)">搜索</el-button></div>
      <p v-if="notice" role="alert" class="exam-field-error">{{ notice }}</p>
      <div v-loading="loading"><article v-for="question in bank.items" :key="question.id" class="bank-selection"><div><small>第 {{ question.chapter }} 章 · {{ objectiveKinds[question.kind] }} · {{ question.id }}</small><p>{{ question.stem }}</p><details><summary>查看选项与题图</summary><p v-for="option in question.options" :key="option.key">{{ option.key }}. {{ option.text }}</p><img v-for="figure in question.images" :key="figure.src" :src="figure.src" :alt="figure.alt" /><p v-if="question.kind === 'cell'">共 {{ question.blank_count }} 空</p></details></div><el-button :disabled="disabled || selected(question.id) || modelValue.length >= 100" @click="add(question)">{{ selected(question.id) ? '已添加' : '添加' }}</el-button></article><p v-if="!bank.items.length" class="op-help">没有符合筛选条件的可用题目。</p></div><ListPager :page="page" :total="bank.total" @change="load" />
    </template>
  </section>
</template>
<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import ListPager from '@/components/ListPager.vue'
import { examObjectiveQuestions } from '@/api/exams'
import { examError } from '@/domain/exams'
import { objectiveKinds } from '@/domain/objectiveExams'
const props = defineProps({modelValue:{type:Array,default:()=>[]}, items:{type:Array,default:()=>[]}, published:Boolean, disabled:Boolean, error:String})
const emit = defineEmits(['update:modelValue'])
const bank = ref({items:[],total:0}), page = ref(1), loading = ref(false), notice = ref(''), known = reactive({})
const filters = reactive({search:'',chapter:null,kind:null})
const chapters = ['进路选择与设备操作','进路取消与人工解锁','模拟行车与正常解锁','故障现象与安全处理','列车进路联锁表','调车进路联锁表']
const total = computed(() => props.modelValue.reduce((sum,item)=>sum+(item.points || 0),0))
watch(()=>props.items, items => items.forEach(item=>{known[item.id]=item}),{immediate:true})
let serial = 0
async function load(number=1) {
  const token = ++serial; loading.value=true; notice.value=''
  try { const result = await examObjectiveQuestions({page:number,search:filters.search,chapter:filters.chapter || undefined,kind:filters.kind || undefined}); if(token!==serial)return; bank.value=result; page.value=number; result.items.forEach(item=>{known[item.id]=item}) }
  catch(error){if(token===serial)notice.value=examError(error)}finally{if(token===serial)loading.value=false}
}
const selected = id => props.modelValue.some(item=>item.question_id===id)
function add(question){if(!selected(question.id))emit('update:modelValue',[...props.modelValue,{question_id:question.id,points:5}])}
function remove(index){emit('update:modelValue',props.modelValue.filter((_,i)=>i!==index))}
function points(index,value){emit('update:modelValue',props.modelValue.map((item,i)=>i===index?{...item,points:value || 1}:item))}
function move(index,delta){const items=[...props.modelValue];[items[index],items[index+delta]]=[items[index+delta],items[index]];emit('update:modelValue',items)}
onMounted(()=>{if(!props.published)load()})
</script>
<style scoped>
.paper-selection{border-block:1px solid #dfe7ef;padding:4px 0 18px;margin:20px 0}.selected-question,.bank-selection{display:flex;align-items:flex-start;justify-content:space-between;gap:18px;padding:16px 0;border-bottom:1px solid #e5edf3}.selected-question:last-child,.bank-selection:last-child{border:0}.selected-question>div:first-child,.bank-selection>div{min-width:0;flex:1}.selected-question p,.bank-selection p{white-space:pre-wrap;line-height:1.8;overflow-wrap:anywhere;margin:8px 0}.selected-controls{display:flex;align-items:center;gap:6px;flex-wrap:wrap;justify-content:flex-end;max-width:280px}.selected-controls .el-button{margin:0}.selected-controls .el-input-number{width:120px}.paper-filters{display:grid;grid-template-columns:2fr 1.5fr 1fr auto;gap:10px}.bank-selection small{color:#586f82}.bank-selection details{font-size:14px;line-height:1.7}.bank-selection summary{cursor:pointer;color:#0075b7}.bank-selection img{max-width:100%;max-height:300px}.invalid{color:#b54732}@media(max-width:850px){.paper-filters{grid-template-columns:1fr 1fr}.selected-question{flex-direction:column}.selected-controls{max-width:none;justify-content:flex-start}}
</style>
