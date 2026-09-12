<template>
  <div class="preview-paper">
    <el-alert title="学生视角试答；试答结果不写入学生成绩。" type="info" :closable="false"/>
    <h2><Notation :text="question.title"/></h2><p class="prompt"><Notation :text="question.prompt"/></p>
    <ul v-if="question.conditions.length"><li v-for="c in question.conditions" :key="c"><Notation :text="c"/></li></ul>
    <ClassicStationCanvas :answer="empty" reference-mode/>
    <form @submit.prevent="tryAnswer">
      <section v-for="f in question.fields" :key="f.id" class="preview-field"><h3><Notation :text="f.label"/><small>{{ f.points }} 分</small></h3>
        <div v-if="f.kind==='choice'||f.kind==='multi'" class="preview-options"><label v-for="option in f.options" :key="option"><input :type="f.kind==='choice'?'radio':'checkbox'" :name="f.id" :value="option" v-model="answers[f.id]"><Notation :text="option"/></label></div>
        <ol v-else-if="f.kind==='order'"><li v-for="(option,i) in answers[f.id]" :key="option"><Notation :text="option"/><button type="button" :aria-label="`上移${option}`" :disabled="i===0" @click="move(f.id,i,-1)">↑</button><button type="button" :aria-label="`下移${option}`" :disabled="i===answers[f.id].length-1" @click="move(f.id,i,1)">↓</button></li></ol>
        <textarea v-else-if="f.kind==='essay'" v-model="answers[f.id]" rows="4" :aria-label="f.label"/>
        <input v-else v-model="answers[f.id]" :aria-label="f.label" type="text">
      </section><el-button native-type="submit" type="primary" :loading="busy">试答并检查评分规则</el-button>
    </form>
    <section v-if="result" class="preview-result"><h3>试答反馈 · 客观项 {{ result.automatic_score }}/{{ result.automatic_max }}</h3><div v-for="f in result.feedback" :key="f.id"><strong><Notation :text="f.label"/></strong><p>{{ f.status==='pending_review'?'待人工评阅':`${f.points}/${f.max_points} 分` }}</p><p v-for="error in f.errors" :key="error"><Notation :text="error"/></p><p v-if="f.expected!==undefined">参考答案：<Notation :text="Array.isArray(f.expected)?f.expected.join(' → '):f.expected" :runs="f.expected_runs"/></p><p v-if="f.explanation" style="white-space:pre-line;overflow-wrap:anywhere"><Notation :text="f.explanation"/></p></div></section>
  </div>
</template>
<script setup>
import {ref,watch} from 'vue'
import Notation from '@/components/RailwayNotation.vue'
import ClassicStationCanvas from '@/components/ClassicExam/ClassicStationCanvas.vue'
import {previewManagedQuestion} from '@/api/management'
const props=defineProps({question:Object,content:Object})
const answers=ref({}),result=ref(null),busy=ref(false),empty={route_buttons:[],switches:{},hostile_signals:[],track_sections:[]}
watch(()=>props.question,question=>{answers.value=Object.fromEntries(question.fields.map(f=>[f.id,f.kind==='order'?[...f.options]:f.kind==='multi'?[]:'']));result.value=null},{immediate:true})
function move(id,i,d){const a=[...answers.value[id]];[a[i],a[i+d]]=[a[i+d],a[i]];answers.value[id]=a}
async function tryAnswer(){busy.value=true;try{result.value=(await previewManagedQuestion(props.content,answers.value)).result}finally{busy.value=false}}
</script>
<style scoped>
.preview-paper{line-height:1.9;color:#395a72}.preview-paper h2{font-size:26px}.prompt{white-space:pre-wrap}.preview-field{padding:18px 0;border-bottom:1px solid #e1eaf2}.preview-field h3{font-size:var(--ui-text-body)}.preview-field small{margin-left:14px;font-weight:normal;color:#586f82}.preview-options{display:flex;flex-wrap:wrap;gap:15px}.preview-options label{display:flex;gap:7px;align-items:center}.preview-field input[type=text],textarea{width:100%;box-sizing:border-box;padding:12px;border:1px solid #c8dbe9;border-radius:5px;font:inherit}.preview-field li{margin:8px 0}.preview-field li button{margin-left:12px}.preview-paper form>.el-button{margin:20px 0}.preview-result{padding:20px;background:#f2f8fc}.preview-result>div{padding:12px 0;border-bottom:1px solid #dce8f0}.preview-result p{margin:5px 0}
</style>
