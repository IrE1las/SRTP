<template>
  <main class="modules-page" v-loading="loading">
    <header class="module-heading"><div><span class="eyebrow">模块一 / 实验一{{ question ? ` / ${question.title}` : '' }}</span><h1>{{ question ? '一号车站 · 操作与观察' : '实验一 · 进路与道岔操作' }}</h1><p>{{ question ? '每一次按钮操作、环境设置与拒绝均保存到本次作答。' : '按小题进入独立场景；连续步骤保持同一条进路。' }}</p></div><router-link :to="question ? '/student/modules/one/experiment-1' : '/student/modules/one'">{{ question ? '返回题目列表' : '返回模块一' }}</router-link></header>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <template v-if="!route.params.questionId">
      <div class="experiment-controls"><label>作答模式 <select v-model="mode"><option value="practice">练习 · 即时反馈</option><option value="exam">考核 · 提交后反馈</option></select></label><button @click="loadRecords">{{ canReview ? '刷新操作记录与学生回放' : '刷新我的记录' }}</button></div>
      <section class="question-list"><article v-for="q in questions" :key="q.id" :class="{pending:q.status !== 'active'}"><span class="status-tag">{{ q.status !== 'active' ? '待教师确认' : q.progress?.status === 'submitted' ? '已完成' : q.progress ? '进行中' : '可开始' }}</span><h2>{{ q.title }}</h2><p>{{ q.public_prompt }}</p><div v-if="q.status === 'active'" class="card-actions"><router-link :to="{path:`/student/modules/one/experiment-1/${q.id}`,query:{mode}}">{{ canReview ? '预览场景' : '开始新作答' }} →</router-link><router-link v-if="q.progress" :to="{path:`/student/modules/one/experiment-1/${q.id}`,query:{attempt:q.progress.attempt_id}}">{{ q.progress.status === 'submitted' ? '查看结果' : '继续作答' }}</router-link></div><p v-else>题设及规则待确认，本期不可启动或计分。</p></article></section>
      <section class="attempt-records"><h2>{{ canReview ? '操作记录与学生回放' : '我的作答记录' }}</h2><p v-if="!records.length">暂无作答记录。</p><article v-for="record in records" :key="record.attempt_id" class="record-row"><div><strong>{{ record.title }}</strong><br /><small>{{ record.student_name }} · {{ record.preview ? '教师预览' : '学生作答' }} · {{ record.status === 'submitted' ? `已提交 · ${record.score} 分` : '进行中' }}</small></div><router-link :to="{path:`/student/modules/one/experiment-1/${record.question_id}`,query:{attempt:record.attempt_id}}">{{ record.status === 'submitted' || record.owner_id !== user.user?.id ? '查看回放' : '继续作答' }} →</router-link></article></section>
    </template>
    <template v-else-if="question && attempt && station">
      <div class="experiment-controls"><span>{{ attempt.mode === 'exam' ? '考核模式' : '练习模式' }} · {{ attempt.status === 'submitted' ? '已提交，只读' : readOnly ? '只读回放' : '进行中' }}</span><div><button :disabled="busy" @click="restore">刷新状态</button> <button v-if="!readOnly" :disabled="busy" @click="newAttempt">另开独立作答</button></div></div>
      <div v-if="replayIndex !== null" class="replay-tools"><strong>只读回放 · 第 {{ replayIndex }} 步</strong><input aria-label="回放进度" type="range" :min="0" :max="events.length" v-model.number="replayIndex" /><select v-if="replayIndex > 0" v-model="replaySide" aria-label="操作前后"><option value="after">操作后</option><option value="before">操作前</option></select><button @click="replayIndex=null;highlight=[]">返回最新状态</button></div>
      <div class="experiment-workspace">
        <section class="diagram-card"><div class="diagram-controls"><strong>一号车站</strong><button aria-label="缩小站场" @click="zoom=Math.max(70,zoom-15)">−</button><span>{{ zoom }}%</span><button aria-label="放大站场" @click="zoom=Math.min(200,zoom+15)">＋</button><button @click="zoom=100">复位视图</button><span>可横向滚动查看全站</span></div><div class="diagram-scroll"><StationDiagram :station="station" :snapshot="displaySnapshot" :selected="displaySnapshot?.selected_buttons || []" :highlight="highlight" :allow-all-buttons="true" :style="{width:`${zoom}%`}" @press="press" @inspect="inspect" @group="selectedGroup=$event" /></div><div class="diagram-legend">蓝色轨道：空闲 · 白色：锁闭 · 红色：占用 · 绿色道岔：定位 · 黄色道岔：反位<br />当前按钮：{{ displaySnapshot?.selected_buttons?.join(' → ') || '未选择' }}</div><div v-if="inspected" class="inspect-note" aria-live="polite">{{ inspected }}</div></section>
        <QuestionPanel :question="question" :mode="attempt.mode" :preview="attempt.preview" :feedback="attempt.feedback">
          <ActionToolbar :station="station" :snapshot="displaySnapshot" :environment="question.allowed_environment_commands" :disabled="busy || readOnly || replayIndex !== null" :selected-group="selectedGroup" @command="command" />
        </QuestionPanel>
      </div>
      <div :class="['operation-message',{rejected:lastResponse?.accepted===false}]" aria-live="polite">{{ lastResponse?.message || displaySnapshot?.last_message }}<span v-if="replayIndex !== null"> · 当前为回放，不能修改</span></div>
      <label class="notes-area">观察与原因说明（保存，不自动计分）<textarea v-model="notes" maxlength="6000" :disabled="readOnly || busy" @input="saveNotes" placeholder="记录看到的道岔、信号和区段变化，以及你的解释。"></textarea></label>
      <div class="experiment-controls"><span>{{ readOnly ? '记录已保存，可逐步查看操作前后状态。' : '操作实时保存；文字草稿保存在本机，提交时一并保存。' }}</span><button v-if="!readOnly" class="primary" :disabled="busy || replayIndex !== null" @click="submit">提交作答</button></div>
      <FeedbackPanel :result="attempt.result" @locate="locate" />
      <section class="timeline"><div class="experiment-controls"><h2>操作事件</h2><button @click="replayIndex=0;replaySide='after'">从初始场景回放</button></div><p v-if="!events.length">尚无操作。请按题干在站场或工具栏中操作。</p><article v-for="(event,index) in events" :key="event.response.event_id" class="timeline-row"><b class="event-order">{{ index+1 }}</b><span>{{ event.response.message }}<br /><time>{{ event.response.accepted ? '操作执行' : '操作拒绝' }} · {{ event.response.route_id ? `${event.response.route_id} 号进路` : event.command.target }} · {{ event.response.occurred_at ? new Date(event.response.occurred_at).toLocaleTimeString() : '' }}</time></span><button @click="showEvent(index)">查看前后状态</button></article></section>
      <details v-if="canReview" class="teacher-config" @toggle="loadConfiguration"><summary>教师查看 · 题目版本与评分配置</summary><p>题目版本 {{ question.question_version }}；教师预览独立保存。</p><pre v-if="configuration">{{ JSON.stringify(configuration,null,2) }}</pre></details>
    </template>
  </main>
</template>
<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/store/user'
import StationDiagram from '@/features/simulationConsole/StationDiagram.vue'
import QuestionPanel from './QuestionPanel.vue'
import ActionToolbar from './ActionToolbar.vue'
import FeedbackPanel from './FeedbackPanel.vue'
import { getQuestions, getStation, createAttempt, getAttempt, getAttempts, sendCommand, submitAttempt, getReplay, getConfiguration } from './api'
import './modules.css'
const route=useRoute(), router=useRouter(), user=useUserStore()
const questions=ref([]),question=ref(null),attempt=ref(null),station=ref(null),records=ref([]),events=ref([]),initial=ref(null)
const loading=ref(false),busy=ref(false),error=ref(''),mode=ref('practice'),notes=ref(''),zoom=ref(100),selectedGroup=ref(''),highlight=ref([]),inspected=ref(''),lastResponse=ref(null),configuration=ref(null)
const replayIndex=ref(null),replaySide=ref('after')
const canReview=computed(()=>['teacher','admin'].includes(user.role))
const readOnly=computed(()=>attempt.value?.status==='submitted'||attempt.value?.owner_id!==user.user?.id)
const displaySnapshot=computed(()=>replayIndex.value===null?attempt.value?.snapshot:replayIndex.value===0?initial.value:replaySide.value==='before'?events.value[replayIndex.value-1]?.before_snapshot:events.value[replayIndex.value-1]?.response.snapshot)
const notesKey=()=>`srtp_module_one_notes_${user.user?.id}_${attempt.value?.attempt_id}`
let generation=0, pendingCommand=null
function saveNotes(){try{localStorage.setItem(notesKey(),notes.value)}catch{}}
async function loadRecords(){try{records.value=await getAttempts()}catch(e){error.value=e.response?.data?.detail||'记录加载失败'}}
async function loadReplay(){const data=await getReplay(attempt.value.attempt_id);events.value=data.events;initial.value=data.initial_snapshot}
async function restore(){if(!attempt.value)return;try{attempt.value=await getAttempt(attempt.value.attempt_id);await loadReplay()}catch(e){error.value=e.response?.data?.detail||'恢复失败'}}
async function boot(){
  const run=++generation; loading.value=true;error.value='';question.value=null;attempt.value=null;events.value=[];lastResponse.value=null;replayIndex.value=null;configuration.value=null;highlight.value=[];pendingCommand=null
  try{
    const list=await getQuestions();if(run!==generation)return;questions.value=list
    if(!route.params.questionId){await loadRecords();return}
    const q=list.find(q=>q.id===route.params.questionId)
    if(!q||q.status!=='active'){error.value=q?'本题待教师确认，尚未开放。':'题目不存在。';return}
    question.value=q;station.value=await getStation();if(run!==generation)return
    const view=route.query.attempt?await getAttempt(route.query.attempt):await createAttempt({question_id:q.id,scenario_id:q.scenario_id,mode:route.query.mode==='exam'?'exam':'practice'})
    if(run!==generation)return
    if(view.question_id!==q.id){error.value='作答记录与题目不匹配。';return}
    attempt.value=view;question.value=view.question
    if(!route.query.attempt)await router.replace({query:{attempt:view.attempt_id}})
    notes.value=view.notes||'';if(view.status==='in_progress'&&view.owner_id===user.user?.id){try{notes.value=localStorage.getItem(notesKey())||notes.value}catch{}}
    await loadReplay()
  }catch(e){error.value=e.response?.data?.detail||'页面加载失败，请返回列表重试。'}finally{if(run===generation)loading.value=false}
}
async function newAttempt(){if(busy.value)return;busy.value=true;try{const view=await createAttempt({question_id:question.value.id,scenario_id:question.value.scenario_id,mode:attempt.value.mode});await router.replace({query:{attempt:view.attempt_id}})}finally{busy.value=false}}
async function command(type,target,payload={}){
  if(busy.value||readOnly.value||replayIndex.value!==null)return
  busy.value=true;error.value=''
  // Retain command identity on a network failure, so retries cannot double-apply.
  const data=pendingCommand||{command_id:crypto.randomUUID(),expected_version:attempt.value.version,type,target,payload}
  pendingCommand=data
  try{const response=await sendCommand(attempt.value.attempt_id,data);pendingCommand=null;lastResponse.value=response;attempt.value={...attempt.value,version:response.after_version,snapshot:response.snapshot,feedback:response.feedback};highlight.value=response.devices||[];await loadReplay()}
  catch(e){error.value=e.response?.data?.detail||'连接中断，下次操作将先重试未确认的命令。';if(e.response){pendingCommand=null;if(e.response.status===409)await restore()}}
  finally{busy.value=false}
}
function press(button){command('PRESS_BUTTON',button,{})}
function inspect(kind,name,text){inspected.value=`${kind} ${name}：${text}`;highlight.value=[name]}
async function submit(){if(busy.value)return;busy.value=true;try{attempt.value=await submitAttempt(attempt.value.attempt_id,{expected_version:attempt.value.version,notes:notes.value});await loadReplay();try{localStorage.removeItem(notesKey())}catch{}}catch(e){error.value=e.response?.data?.detail||'提交失败，请重试。'}finally{busy.value=false}}
function showEvent(index){replayIndex.value=index+1;replaySide.value='after';highlight.value=events.value[index].response.devices||[];lastResponse.value=null;window.scrollTo({top:0,behavior:'smooth'})}
function locate(checkpoint){const index=events.value.findIndex(e=>e.response.event_id===checkpoint.event_id);if(index>=0)showEvent(index);highlight.value=checkpoint.devices||[]}
async function loadConfiguration(event){if(event.target.open&&!configuration.value){try{configuration.value=await getConfiguration(question.value.id)}catch(e){error.value='教师配置读取失败'}}}
watch(()=>[route.params.questionId,route.query.attempt],()=>{if(route.query.attempt && route.query.attempt === attempt.value?.attempt_id && route.params.questionId === question.value?.id)return;boot()},{immediate:true})
</script>
