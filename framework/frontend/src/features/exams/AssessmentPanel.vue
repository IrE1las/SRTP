<template>
  <section class="exam-form-section assessment-panel" aria-labelledby="assessment-title">
    <h2 id="assessment-title">过程评价</h2>
    <p v-if="!evaluation" class="op-help">本场未启用接车进路过程评价，继续按原流程人工批阅。</p>
    <template v-else-if="evaluation.status !== 'ready'"><el-alert title="证据需要人工复核，未生成自动分数" type="warning" :closable="false" /><p>{{ evaluation.reason }}</p></template>
    <template v-else>
      <div class="assessment-score"><strong>{{ evaluation.suggested_score }}<small> / 100</small></strong><span>后端建议分 · 最终成绩由教师确认</span></div>
      <dl class="assessment-dimensions"><div><dt>任务完成</dt><dd>{{ evaluation.dimensions.task }} / 60</dd></div><div><dt>操作规范</dt><dd>{{ evaluation.dimensions.procedure }} / 30</dd></div><div><dt>操作熟练</dt><dd>{{ evaluation.dimensions.fluency }} / 10</dd></div></dl>
      <p v-for="reason in evaluation.cap_reasons" :key="reason" class="assessment-cap">{{ reason }}，本题最高 {{ evaluation.cap }} 分。</p>
      <ul class="assessment-goals"><li v-for="item in goals" :key="item.key">{{ evaluation.milestones[item.key] ? '已完成' : '未取得' }} · {{ item.label }}</li></ul>
      <p v-if="!evaluation.episodes.length" class="op-help">未发现已确认的扣分事件。</p>
      <ol v-else class="assessment-episodes"><li v-for="(item,index) in evaluation.episodes" :key="index"><div><strong>{{ item.message }}</strong><span>扣 {{ item.points }} 分 · {{ item.recovered ? '已恢复或已结束' : '恢复情况见证据' }}</span></div><el-button link @click="inspect(item.evidence)">查看操作</el-button></li></ol>
      <el-button @click="$emit('adopt', evaluation.suggested_score)">采用建议分到成绩草稿</el-button>
      <p class="op-help">保存最终成绩后，可确认本次评价并生成学生评语；调整建议分时须填写理由。AI不参与评分。</p>
      <el-input v-model="reason" type="textarea" :rows="2" maxlength="2000" aria-label="评价核对或人工调整理由" placeholder="核对说明；人工调整成绩时必填" />
      <div class="assessment-actions"><el-button :disabled="dirty || grade.score == null || busy" @click="confirm">确认评价事实与已保存成绩</el-button><el-button :disabled="dirty || !reviewed || busy" :loading="busy" @click="generate">生成学生评语草稿</el-button></div>
      <p v-if="notice" role="status" class="op-help">{{ notice }}</p>
      <template v-if="text"><p class="op-preserve">{{ text }}</p><el-button :disabled="dirty || !reviewed" @click="$emit('comment',text)">将评语放入草稿，核对后发布</el-button></template>
    </template>
    <el-dialog v-model="showEvidence" title="相关操作证据" width="min(760px,94vw)"><template v-if="evidence"><section v-for="row in evidence" :key="row.sequence"><h3>{{ beijingTime(row.at) }}</h3><OperationLog v-if="row.source" :events="[row.source]" /><p v-for="(item,index) in row.events" :key="index">{{ item.message }}</p></section></template><p v-else>正在加载证据…</p></el-dialog>
  </section>
</template>
<script setup>
import { computed, ref, watch } from 'vue'
import OperationLog from '@/features/operationQuestions/OperationLog.vue'
import { reviewAssessment, generateStudentCommentary, getAssessmentEvidence } from '@/api/operationAssessment'
import { beijingTime } from '@/domain/exams'
const props=defineProps({sid:{type:String,required:true},evaluation:Object,grade:{type:Object,required:true},dirty:Boolean,review:Object})
defineEmits(['adopt','comment'])
const reason=ref(''),notice=ref(''),busy=ref(false),confirmedRevision=ref(null),text=ref(''),showEvidence=ref(false),evidence=ref(null)
const reviewed=computed(()=>confirmedRevision.value===props.grade.revision || props.review?.grade_revision===props.grade.revision)
watch(()=>[props.grade.revision,props.evaluation?.id],()=>{text.value='';confirmedRevision.value=null})
const goals=[{key:'A1',label:'有效目标办理请求（10分）'},{key:'A2',label:'目标进路锁闭（20分）'},{key:'A3',label:'规定信号允许（20分）'},{key:'A4',label:'结束状态正确（10分）'}]
async function confirm(){busy.value=true;notice.value='';try{await reviewAssessment(props.sid,{evaluation_id:props.evaluation.id,grade_revision:props.grade.revision,reason:reason.value});confirmedRevision.value=props.grade.revision;notice.value='本次评价已确认，可生成评语或直接手写评语。'}catch(e){notice.value=e.response?.data?.detail || '确认失败，请刷新核对'}finally{busy.value=false}}
async function generate(){busy.value=true;notice.value='';try{const result=await generateStudentCommentary(props.sid,props.grade.revision);text.value=result.text || '';notice.value=result.status==='ready'?'评语尚未发布，请核对后放入成绩草稿。':'评语暂不可用，可直接手写，不影响成绩发布。'}catch(e){notice.value=e.response?.data?.detail || '评语生成失败，可直接手写'}finally{busy.value=false}}
async function inspect(sequences){showEvidence.value=true;evidence.value=null;try{const selected=[...new Set([...sequences.slice(0,2),sequences.at(-1)])];const rows=await Promise.all(selected.map(sequence=>getAssessmentEvidence(props.sid,sequence-1)));evidence.value=rows.flatMap(row=>row.items)}catch{notice.value='证据加载失败，请重试';showEvidence.value=false}}
</script>
<style scoped>
.assessment-panel{line-height:1.8}.assessment-score{display:flex;align-items:baseline;gap:20px;flex-wrap:wrap}.assessment-score strong{font-size:32px;color:#175b84}.assessment-score small{font-size:15px;font-weight:400}.assessment-score span{color:#617b8f;font-size:13px}.assessment-dimensions{display:flex;gap:36px;flex-wrap:wrap;margin:18px 0}.assessment-dimensions dt{font-size:13px;color:#617b8f}.assessment-dimensions dd{margin:4px 0;font-size:19px}.assessment-cap{color:#a05b2d}.assessment-goals{padding-left:22px}.assessment-episodes{padding-left:22px}.assessment-episodes li{padding:12px 0;border-bottom:1px solid #e1e9ef;display:flex;gap:12px;justify-content:space-between}.assessment-episodes span{display:block;font-size:13px;color:#617b8f}.assessment-actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:14px}.assessment-actions .el-button{margin-left:0}
</style>
