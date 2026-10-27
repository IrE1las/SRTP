<template>
  <section class="lab-page" v-loading="loading">
    <header class="lab-header"><div><router-link :to="THEORY_ROOT">返回</router-link><h1>{{ activeTopic?.title || '理论专题' }}</h1><p>{{ theoryPlatformName(topicId) }}</p></div><router-link class="history-link" :to="theoryHistoryPath(topicId)">我的作答 →</router-link></header>
    <p v-if="notice" class="notice" role="alert">{{ notice }}</p>
    <div class="question-tabs" aria-label="专题内题目"><button v-for="q in questionPageView.items" :key="q.key" :disabled="submitting" :class="{active:selectedKey===q.key}" @click="chooseQuestion(q.key)"><span>{{ String(q.sequence).padStart(2,'0') }}</span><Notation :text="q.title"/><small v-if="attempts.some(a=>a.question_id===q.id)">已提交</small></button></div>
    <ListPager v-if="questionPageView.total>LIST_PAGE_SIZE" :page="questionPageView.page" :total="questionPageView.total" @change="changeQuestionPage"/>
      <article v-if="question" class="workspace" :aria-busy="submitting">
        <div class="question-title"><div><span class="tag">{{ question.level }} · {{ question.kinds.join(' / ') }}</span><h2><Notation :text="question.title"/></h2></div><span class="grading-label">客观项 {{ question.automatic_max }} 分<br>教师评阅 {{ question.manual_max }} 分</span></div>
        <p class="prompt"><Notation :text="question.prompt"/></p>
        <aside v-if="question.conditions.length" class="conditions"><strong>本题条件</strong><p v-for="condition in question.conditions" :key="condition"><Notation :text="condition"/></p></aside>
        <TheorySimulationConsole v-if="theoryPlatform(question.topic)==='simulation-console'" :key="question.key" :question-key="question.key"/>
        <section v-else class="table-platform" aria-label="联锁表仿真平台"><h3>联锁表仿真平台</h3><div class="diagram-wrap"><TheoryStationCanvas :answer="emptyDiagram" :focus="focus" reference-mode @inspect="inspect"/><div class="device-readout"><span v-if="focus"><Notation :text="focus.code"/> · {{ deviceDescription }}</span><span v-else>点选设备查看名称和位置，按题目填写联锁表。</span></div></div></section>
        <form @submit.prevent="submit" class="answer-form">
          <div class="form-caption"><h3>实验作答</h3><span>填写栏保留（反位）、[防护]、{带动}及 &lt;条件&gt;；下标显示不改变设备编号。</span></div>
          <fieldset :disabled="submitting">
            <section v-for="(field,index) in question.fields" :key="field.id" :id="`field-${field.id}`" class="answer-field">
              <div class="field-heading"><label :for="`answer-${field.id}`"><span>{{ index+1 }}</span><Notation :text="field.label"/></label><small>{{ field.kind==='essay' ? '教师评阅' : '自动核对' }} · {{ field.points }}分</small></div>
              <div v-if="field.kind==='choice'" class="choice-group" role="radiogroup" :aria-label="field.label"><label v-for="option in field.options" :key="option" :class="{selected:answers[field.id]===option}"><input type="radio" :name="field.id" :value="option" v-model="answers[field.id]"><Notation :text="option"/></label></div>
              <div v-else-if="field.kind==='multi'" class="choice-group"><label v-for="option in field.options" :key="option" :class="{selected:answers[field.id]?.includes(option)}"><input type="checkbox" :value="option" v-model="answers[field.id]"><Notation :text="option"/></label></div>
              <ol v-else-if="field.kind==='order'" class="order-list"><li v-for="(option,i) in answers[field.id]" :key="option"><span>{{ i+1 }}.</span><Notation :text="option"/><button type="button" :aria-label="`上移${option}`" :disabled="i===0" @click="move(field.id,i,-1)">↑</button><button type="button" :aria-label="`下移${option}`" :disabled="i===answers[field.id].length-1" @click="move(field.id,i,1)">↓</button></li></ol>
              <template v-else-if="field.kind==='cell'"><input :id="`answer-${field.id}`" type="text" v-model="answers[field.id]" maxlength="6000" autocomplete="off" placeholder="按原图填写设备和符号"><p v-if="answers[field.id]" class="notation-preview">记号预览：<Notation :text="answers[field.id]"/></p></template>
              <template v-else><textarea :id="`answer-${field.id}`" v-model="answers[field.id]" rows="4" maxlength="6000" placeholder="按工况逐项记录：条件 → 现象 → 原因。区分实测与推测，并写出依据。"></textarea><div class="word-count">{{ (answers[field.id]||'').length }} / 6000</div></template>
            </section>
          </fieldset>
          <div class="submit-row"><p>{{ draftMessage }}<br><small>记录与论述由教师评阅；自动核对结果不代表实验现象已得到验证。</small></p><button type="submit" class="primary-button" :disabled="submitting">{{ submitting?'正在保存…':'提交作答 →' }}</button></div>
        </form>
        <section v-if="result" class="feedback" aria-live="polite" ref="feedbackPanel"><h3>作答已保存 · {{ result.result.status==='pending_review'?'等待教师评阅':'评阅完成' }}</h3><p v-if="result.result.automatic_max">客观项 {{ result.result.automatic_score }} / {{ result.result.automatic_max }} 分<span v-if="result.result.status==='pending_review'">；论述部分尚未计分。</span></p><p v-else>本题为记录与论述题，保存成功后由教师评阅，不自动判定正确或错误。</p><div v-for="item in result.result.feedback" :key="item.id" :class="['feedback-item',item.status]"><strong>{{ item.status==='correct'?'✓':item.status==='incorrect'?'需调整':item.status==='partial'?'部分得分':'待评阅' }} · <Notation :text="item.label"/></strong><template v-if="item.status!=='pending_review'"><p v-for="error in item.errors" :key="error"><Notation :text="error"/></p><p>参考填写：<Notation :text="Array.isArray(item.expected)?item.expected.join(' → '):item.expected" :runs="item.expected_runs"/></p><p><Notation :text="item.explanation"/></p><button v-if="item.status==='incorrect'" @click="locateField(item.id)">回到本栏修改 ↑</button></template><template v-else><p>{{ item.message }}</p><p v-if="item.explanation" class="manual-reference"><Notation :text="item.explanation"/></p><ul><li v-for="point in item.criteria" :key="point">{{ point }}</li></ul></template></div></section>
      </article>
    <el-empty v-if="!loading&&!question" description="null"/>
  </section>
</template>
<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/store/user'
import TheoryStationCanvas from '@/components/theory/TheoryStationCanvas.vue'
import TheorySimulationConsole from '@/features/simulationConsole/TheorySimulationConsole.vue'
import Notation from '@/components/RailwayNotation.vue'
import ListPager from '@/components/ListPager.vue'
import { paginate,LIST_PAGE_SIZE } from '@/domain/pagination'
import { topology } from '@/domain/theoryStation'
import { THEORY_ROOT, theoryPlatform, theoryPlatformName, theoryHistoryPath } from '@/domain/theoryNavigation'
import { getLabQuestions,getLabQuestion,getLabAttempts,submitLabAnswer } from '@/api/labTopics'
const route=useRoute(),router=useRouter(),user=useUserStore()
const questions=ref([]),question=ref(null),attempts=ref([]),answers=ref({}),selectedKey=ref('')
const loading=ref(false),submitting=ref(false),notice=ref(''),result=ref(null),focus=ref(null),feedbackPanel=ref(null),draftMessage=ref('')
const topicId=computed(()=>Number(route.params.topicId))
const topicQuestions=computed(()=>questions.value.filter(q=>q.topic===topicId.value))
const questionPage=ref(1)
const questionPageView=computed(()=>paginate(topicQuestions.value,questionPage.value))
async function changeQuestionPage(value){const rows=paginate(topicQuestions.value,value).items;if(rows[0])await chooseQuestion(rows[0].key)}
const activeTopic=computed(()=>topicQuestions.value[0]?.topic_info)
const emptyDiagram={route_buttons:[],switches:{},hostile_signals:[],track_sections:[]}
const deviceDescription=computed(()=>{
  const s=topology.signals.find(s=>s.name===focus.value?.code)
  if(s)return s.type+'信号机 · '+s.track+'股道'
  const w=topology.switches.find(w=>w.id===focus.value?.code)
  if(w)return w.type+' · 连接'+w.connects.join('与')+'股道'
  const section=topology.sections.find(s=>s.name===focus.value?.code)
  return section?'轨道区段 · '+section.track+'股道':'原图参考设备'
})
let requestId=0,revision=0,initializing=false,loadId=0
function draftKey(q=question.value){return 'srtp_lab_'+user.user?.id+'_'+q?.key+'_'+q?.fingerprint}
function inspect(kind,code){focus.value={kind,code}}
function saveDraft(){if(!question.value||initializing)return;try{localStorage.setItem(draftKey(),JSON.stringify(answers.value));draftMessage.value='草稿已保存到本机。'}catch{draftMessage.value='本机草稿保存失败，请及时提交。'}}
watch(answers,()=>{if(initializing)return;revision++;result.value=null;saveDraft()},{deep:true,flush:'sync'})
function message(e,fallback){const detail=e.response?.data?.detail;return typeof detail==='string'?detail:fallback}
async function chooseQuestion(key,updateUrl=true){
  if(submitting.value||!topicQuestions.value.some(q=>q.key===key))return
  questionPage.value=Math.floor(topicQuestions.value.findIndex(q=>q.key===key)/LIST_PAGE_SIZE)+1
  saveDraft();const current=++requestId
  loading.value=true;notice.value='';result.value=null;focus.value=null;question.value=null
  try{
    const q=await getLabQuestion(key)
    if(current!==requestId)return
    if(q.topic!==topicId.value)throw new Error('专题不匹配')
    initializing=true;question.value=q;selectedKey.value=key
    let draft=null;try{draft=JSON.parse(localStorage.getItem(draftKey(q)))}catch{}
    answers.value=Object.fromEntries(q.fields.map(f=>[f.id,draft?.[f.id]??(f.kind==='multi'?[]:f.kind==='order'?[...f.options]:'')]))
    initializing=false;revision++;draftMessage.value=draft?'已恢复本题草稿。':'草稿保存在本机，提交后保存。'
    if(updateUrl)await router.replace({path:route.path,query:{q:key}})
  }catch(e){if(current===requestId)notice.value=message(e,'题目加载失败，可重试。')}
  finally{if(current===requestId){loading.value=false;initializing=false}}
}
async function loadTopic(){
  const current=++loadId;++requestId
  saveDraft();question.value=null;loading.value=true
  try{
    if(!questions.value.length)questions.value=await getLabQuestions()
    if(current!==loadId)return
    const key=topicQuestions.value.find(q=>q.key===route.query.q)?.key||topicQuestions.value[0]?.key
    if(key)await chooseQuestion(key)
    const rows=await getLabAttempts(topicId.value)
    if(current===loadId)attempts.value=rows
  }catch(e){if(current===loadId)notice.value=message(e,'专题加载失败。')}
  finally{if(current===loadId)loading.value=false}
}
function move(id,index,offset){const values=[...answers.value[id]];[values[index],values[index+offset]]=[values[index+offset],values[index]];answers.value[id]=values}
function locateField(id){document.getElementById('field-'+id)?.scrollIntoView({behavior:'smooth',block:'center'});document.getElementById('answer-'+id)?.focus({preventScroll:true})}
async function submit(){
  if(!question.value||submitting.value)return
  const missing=question.value.fields.find(f=>Array.isArray(answers.value[f.id])?!answers.value[f.id].length:!String(answers.value[f.id]??'').trim())
  if(missing){notice.value='请完成全部答题栏后提交。';locateField(missing.id);return}
  const q=question.value,snapshot=JSON.parse(JSON.stringify(answers.value)),rev=revision
  submitting.value=true;notice.value=''
  try{const response=await submitLabAnswer(q.key,{fingerprint:q.fingerprint,answers:snapshot});attempts.value.unshift(response)
    if(rev===revision&&question.value?.key===q.key){result.value=response;await nextTick();feedbackPanel.value?.scrollIntoView({behavior:'smooth',block:'start'})}
  }catch(e){notice.value=message(e,'提交失败，答案已保留，可重试。')}finally{submitting.value=false}
}
watch(()=>route.params.topicId,loadTopic)
watch(()=>route.query.q,key=>{if(typeof key==='string'&&key!==selectedKey.value&&!submitting.value)chooseQuestion(key,false)})
onMounted(loadTopic)
</script>
<style scoped>
.manual-reference{white-space:pre-line;overflow-wrap:anywhere;line-height:1.9}
.lab-page{max-width:1550px;margin:auto;color:#19334d}.lab-header{display:flex;justify-content:space-between;gap:24px;align-items:center;margin-bottom:22px}.overline{color:#337796;font-size:var(--ui-text-meta);letter-spacing:2px;margin:0 0 8px}.lab-header h1{font-size:32px;margin:0 0 10px}.lab-header p:last-child{margin:0;color:#738497;line-height:1.8}.header-actions{display:flex;flex-direction:column;align-items:flex-end;gap:12px}.count{font-size:var(--ui-text-base);color:#52728a}button{font:inherit;border:1px solid #dce6ee;border-radius:6px;padding:8px 12px;background:white;color:#42677e;cursor:pointer}button:disabled{opacity:.5;cursor:default}.mode-tabs{display:flex;gap:8px;border-bottom:1px solid #dfe7ee;margin-bottom:22px;padding-bottom:10px}.mode-tabs button{border:none;background:transparent}.mode-tabs button.active{color:#006fa9;background:#e6f2fa}.mode-tabs span{font-size:var(--ui-text-meta);margin-left:6px}.topic-grid{display:flex;flex-direction:column;gap:12px}.topic-card{display:flex;align-items:center;gap:12px;text-align:left;padding:17px 13px;min-height:88px}.topic-card.active{background:#edf6fc;border-color:#54a0c7;box-shadow:inset 3px 0 #0075b7}.topic-num{font:27px Georgia;color:#586f82}.topic-card strong{display:block;font-weight:600;font-size:var(--ui-text-base);line-height:1.6}.topic-card small{display:block;font-size:var(--ui-text-sm);color:#586f82;margin-top:7px}.topic-arrow{margin-left:auto;color:#586f82}.topic-intro{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:26px 0 18px}.topic-intro h2{font-size:var(--ui-text-heading);margin:0 0 8px}.topic-intro p{font-size:var(--ui-text-base);color:#738497;line-height:1.8;margin:0}.topic-intro>span{font-size:var(--ui-text-meta);white-space:nowrap;color:#586f82}.question-tabs{display:flex;gap:10px;margin-bottom:18px}.question-tabs button{flex:1;text-align:left;display:flex;align-items:center;gap:10px;padding:12px}.question-tabs button>span:first-child{color:#586f82;font-size:var(--ui-text-base)}.question-tabs button.active{border-color:#7fb3d3;color:#006fa9;background:#f4faff}.question-tabs small{color:#528579;font-size:var(--ui-text-sm);white-space:nowrap;margin-left:auto}.workspace{background:white;border:1px solid #dfe7ee;padding:26px;border-radius:10px}.question-title{display:flex;justify-content:space-between;gap:20px;align-items:center}.question-title h2{font-size:25px;margin:12px 0}.tag{font-size:var(--ui-text-meta);color:#407c9a}.grading-label{font-size:var(--ui-text-meta);line-height:1.9;white-space:nowrap;color:#586f82}.prompt{font-size:var(--ui-text-body);line-height:2;color:#50697e;margin:10px 0 18px}.conditions{padding:14px 18px;background:#fff9ee;border:1px solid #eeddbb;border-radius:7px;margin-bottom:18px;font-size:var(--ui-text-base);line-height:1.9;color:#805f34}.conditions p{margin:4px 0}.diagram-wrap{margin:18px 0}.device-readout{padding:11px 14px;border:1px solid #dfe7ee;background:#f5f9fc;border-radius:0 0 6px 6px;font-size:var(--ui-text-base);color:#69849a;min-height:40px}.interval-context{display:flex;align-items:center;flex-wrap:wrap;gap:18px;border:1px dashed #7fa4ba;padding:17px;background:#f4f9fc;border-radius:7px;font-size:var(--ui-text-base)}.interval-line{flex:1;text-align:center;border-bottom:3px double #839cae;font-size:24px}.interval-context small{width:100%;color:#586f82;font-size:var(--ui-text-meta)}.form-caption{display:flex;justify-content:space-between;gap:15px;align-items:baseline;margin-top:25px}.form-caption h3{font-size:var(--ui-text-lead)}.form-caption span{font-size:var(--ui-text-meta);color:#586f82;line-height:1.7}.answer-form fieldset{padding:0;margin:0;border:0;min-width:0}.answer-field{padding:20px 0;border-top:1px solid #e6edf3;scroll-margin-top:24px}.field-heading{display:flex;justify-content:space-between;gap:12px;margin-bottom:12px}.field-heading label{font-size:var(--ui-text-base);color:#405d72;line-height:1.8}.field-heading label>span:first-child{display:inline-block;text-align:center;min-width:22px;margin-right:10px;background:#eaf3f9;color:#4585a3;border-radius:4px}.field-heading small{font-size:var(--ui-text-sm);color:#586f82;white-space:nowrap;line-height:2.4}.choice-group{display:flex;flex-wrap:wrap;gap:10px}.choice-group label{display:flex;align-items:center;gap:8px;border:1px solid #dce5ed;padding:10px 14px;border-radius:6px;font-size:var(--ui-text-base);cursor:pointer}.choice-group label.selected{border-color:#58a0c7;background:#edf7fc}.choice-group input{accent-color:#0075b7}.answer-field input[type=text],textarea{box-sizing:border-box;width:100%;border:1px solid #d3e0e9;border-radius:6px;padding:11px 13px;font:inherit;font-size:var(--ui-text-base);color:#2f4d64;background:#fcfdff;line-height:1.9}textarea{resize:vertical;min-height:110px}.word-count{text-align:right;font-size:var(--ui-text-sm);color:#586f82;margin-top:5px}.notation-preview{font-size:var(--ui-text-base);color:#426c84;margin:10px 0 0}.order-list{list-style:none;margin:0;padding:0;max-width:680px;display:grid;gap:7px}.order-list li{display:flex;align-items:center;gap:12px;background:#f6f9fc;border:1px solid #e4ebf1;border-radius:5px;padding:8px 12px;font-size:var(--ui-text-base)}.order-list li>span:nth-child(2){flex:1}.order-list button{padding:4px 11px}.submit-row{border-top:1px solid #e1e9f0;padding-top:20px;display:flex;align-items:center;justify-content:space-between;gap:18px}.submit-row p{font-size:var(--ui-text-base);color:#597b91;line-height:1.9;margin:0}.submit-row small{color:#586f82}.primary-button{background:#0075b7;border-color:#0075b7;color:white;padding:12px 24px;white-space:nowrap}.notice{background:#fff0e6;border:1px solid #edcdb9;border-radius:7px;padding:12px 15px;color:#995333;font-size:var(--ui-text-base)}.feedback{border-top:1px solid #dce7ef;margin-top:24px;padding-top:18px;scroll-margin-top:20px}.feedback>p{color:#648092;line-height:1.9;font-size:var(--ui-text-base)}.feedback-item{border:1px solid #dfe8ef;border-left:3px solid #91abba;border-radius:5px;background:#fafcfe;padding:14px;margin-top:10px;font-size:var(--ui-text-base);line-height:1.9}.feedback-item.correct{border-left-color:#48a48a}.feedback-item.incorrect{border-left-color:#d08b5c;background:#fffaf5}.feedback-item p{margin:6px 0;color:#627a8d}.feedback-item ul{color:#586f82;margin:6px 0;padding-left:20px}.feedback-item button{font-size:var(--ui-text-meta);padding:4px 8px}.source-note{margin-top:22px;color:#586f82;font-size:var(--ui-text-meta);line-height:1.9}.source-note summary{cursor:pointer}.records-heading{display:flex;justify-content:space-between;align-items:center}.record{margin:16px 0;padding:22px;background:white;border:1px solid #dfe8ef;border-radius:8px;line-height:1.8}.record header{display:flex;justify-content:space-between;gap:15px}.record header span{font-size:var(--ui-text-meta);color:#586f82;white-space:nowrap}.record>small{color:#586f82;font-size:var(--ui-text-meta)}.record details summary{cursor:pointer;font-size:var(--ui-text-base);color:#537c94}.record p{font-size:var(--ui-text-base)}.history-field{padding:15px 0;border-top:1px solid #e7edf2;white-space:pre-wrap;font-size:var(--ui-text-base)}.history-field strong{font-size:var(--ui-text-base)}.history-field input[type=number]{width:80px;border:1px solid #cbdce8;border-radius:4px;padding:7px}.history-field ul{color:#586f82;white-space:normal}.record textarea{margin:9px 0}.teacher-comment{background:#edf6fb;padding:12px;border-radius:5px}.muted{color:#586f82}.original-photo{width:100%;max-height:78vh}button:focus-visible,input:focus-visible,textarea:focus-visible{outline:3px solid #82bfe0;outline-offset:2px}
@media(max-width:1100px){.topic-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.question-tabs{flex-direction:column}.question-tabs button{flex:auto}.form-caption{flex-direction:column;gap:0}.workspace{padding:20px}}
@media(max-width:600px){.lab-header{flex-direction:column;align-items:flex-start;gap:15px}.header-actions{align-items:flex-start}.topic-card{gap:7px;padding:12px 10px}.topic-num{font-size:23px}.topic-card strong{font-size:var(--ui-text-base)}.topic-arrow{display:none}.topic-intro{flex-direction:column;align-items:flex-start}.workspace{padding:15px}.question-title{align-items:flex-start}.question-title h2{font-size:var(--ui-text-heading)}.field-heading{flex-direction:column;gap:0}.submit-row{align-items:stretch;flex-direction:column}.record{padding:15px}.record header{flex-direction:column;gap:3px}.diagram-wrap :deep(.theory-station){min-width:0}.diagram-wrap :deep(.board-toolbar){flex-direction:column;align-items:flex-start;gap:12px}.diagram-wrap :deep(.zoom-tools){white-space:nowrap}.mode-tabs{gap:3px}.mode-tabs button{padding:9px}.interval-context{gap:10px}.topic-grid{gap:8px}}
</style>

<style scoped>.history-link{color:#0075b7;text-decoration:none;border:1px solid #b8d9eb;border-radius:6px;padding:12px 20px}.table-platform h3{color:#19334d}.workspace{min-width:0}</style>
