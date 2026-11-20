<template>
  <div class="objective-sitting">
    <aside class="answer-navigation" aria-label="答题进度"><h2>答题卡</h2><p>已答 {{ completed }} / {{ questions.length }} 题</p><div class="answer-numbers"><button v-for="(question,index) in questions" :key="question.id" :class="{answered:answered(question,answers[question.id])}" :aria-label="`第${index+1}题，${answered(question,answers[question.id])?'已答':'未答'}`" @click="jump(question.id)">{{ index+1 }}</button></div><p role="status">{{ saving ? '正在保存答案…' : dirty ? '有尚未保存的答案' : '答案已保存到服务器' }}</p><p class="op-help">每题全部答对得分。修改后自动保存，交卷前会再次保存。</p><p v-if="error" role="alert" class="exam-field-error">{{ error }}</p><el-button :loading="saving" :disabled="disabled" @click="retry">保存答案</el-button><el-button :disabled="saving || disabled" @click="refresh">重新读取答案</el-button></aside>
    <ObjectivePaper :questions="questions" :answers="answers" :disabled="disabled" @answer="edit" />
  </div>
</template>
<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ElMessageBox } from 'element-plus'
import ObjectivePaper from './ObjectivePaper.vue'
import { getExamAttempt, saveObjectiveAnswers } from '@/api/exams'
import { examError } from '@/domain/exams'
import { answered } from '@/domain/objectiveExams'
const props = defineProps({attempt:{type:Object,required:true},disabled:Boolean})
const emit = defineEmits(['saved'])
const questions = computed(()=>props.attempt.question.items)
const answers = ref(JSON.parse(JSON.stringify(props.attempt.answers || {}))), revision = ref(props.attempt.answer_revision)
const saved = ref(JSON.stringify(answers.value)), saving = ref(false), error = ref('')
const dirty = computed(()=>JSON.stringify(answers.value)!==saved.value)
const completed = computed(()=>questions.value.filter(question=>answered(question,answers.value[question.id])).length)
const key = 'srtp-exam-answers-' + props.attempt.session_id
let timer, inFlight = null, disposed = false
try {
  const local = JSON.parse(localStorage.getItem(key) || 'null')
  if(local && local.answers && typeof local.revision==='number'){
    answers.value=local.answers; revision.value=local.revision
    if(JSON.stringify(local.answers)!==saved.value)error.value='已恢复本机未确认答案，将在保存时核对服务器版本。'
    else revision.value=props.attempt.answer_revision
  }
} catch { error.value='未能读取本机备份，请核对当前答案。' }
function backup(){try{localStorage.setItem(key,JSON.stringify({answers:answers.value,revision:revision.value}))}catch{error.value='本机备份未成功，请点击保存答案并核对服务器状态。'}}
function edit(id,value){if(props.disabled)return;answers.value={...answers.value,[id]:value};backup();clearTimeout(timer);timer=setTimeout(()=>{if(!props.disabled)flush().catch(()=>{})},700)}
async function flush(){
  if(inFlight){await inFlight;if(dirty.value)return flush();return revision.value}
  if(!dirty.value)return revision.value
  if(props.attempt.status!=='active')throw new Error('考试已结束')
  saving.value=true;error.value=''
  inFlight=(async()=>{
    while(dirty.value && !disposed){
      const payload=JSON.parse(JSON.stringify(answers.value)), snapshot=JSON.stringify(payload)
      const result=await saveObjectiveAnswers(props.attempt.session_id,{revision:revision.value,answers:payload})
      revision.value=result.answer_revision;saved.value=snapshot;backup();emit('saved',result)
      if(result.status==='submitted')break
    }
    return revision.value
  })()
  try{return await inFlight}catch(cause){error.value=examError(cause,'答案尚未保存，请保留页面并重试。');throw cause}finally{inFlight=null;saving.value=false}
}
async function retry(){try{await flush()}catch{/* keep the local draft */}}
async function refresh(){
  if(dirty.value){try{await ElMessageBox.confirm('重新读取会覆盖本页尚未保存的答案。确认使用服务器已保存的答案？','重新读取答案',{confirmButtonText:'重新读取',cancelButtonText:'保留本页答案'})}catch{return}}
  try{const result=await getExamAttempt(props.attempt.session_id);answers.value=JSON.parse(JSON.stringify(result.answers));revision.value=result.answer_revision;saved.value=JSON.stringify(answers.value);error.value='';backup();emit('saved',result)}catch(cause){error.value=examError(cause)}
}
function jump(id){document.getElementById('paper-question-'+id)?.focus()}
watch(()=>props.disabled, disabled=>{if(!disabled && dirty.value)flush().catch(()=>{})},{immediate:true})
defineExpose({flush,refresh,dirty,completed})
onBeforeUnmount(()=>{disposed=true;clearTimeout(timer)})
</script>
<style scoped>
.objective-sitting{display:grid;grid-template-columns:220px minmax(0,1fr);gap:20px;margin-top:20px;align-items:start}.answer-navigation{position:sticky;top:16px;background:white;border-top:3px solid #093278;padding:20px}.answer-navigation h2{font-size:18px;margin:0}.answer-navigation p{font-size:14px;line-height:1.8}.answer-numbers{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;max-height:45vh;overflow:auto}.answer-numbers button{min-height:36px;border:1px solid #aabcca;background:white;color:#19334d;cursor:pointer}.answer-numbers button.answered{background:#093278;color:#fff;border-color:#093278}.answer-numbers button:focus-visible{outline:3px solid #0075b7;outline-offset:2px}.answer-navigation .el-button{margin:8px 4px 0 0}@media(max-width:800px){.objective-sitting{grid-template-columns:1fr}.answer-navigation{position:static}.answer-numbers{grid-template-columns:repeat(auto-fill,minmax(36px,1fr));max-height:140px}}
</style>
