<template>
  <section class="op-panel" aria-labelledby="assessment-config-title">
    <h2 id="assessment-config-title">操作考试评价</h2>
    <p class="op-help">首期支持正常办理一条接车进路。任务完成60分、操作规范30分、操作熟练10分；由后端评分，教师确认发布。AI仅可生成学生评语。</p>
    <el-alert v-if="notice" :title="notice" :type="failed ? 'error' : 'success'" :closable="false" />
    <el-form v-if="ready" label-position="top" :disabled="locked || busy">
      <el-form-item label="评价方式"><el-switch v-model="form.enabled" active-text="接车进路过程评价" inactive-text="人工批阅" /></el-form-item>
      <template v-if="form.enabled">
        <el-form-item label="目标接车进路"><el-select v-model="form.route_ids" multiple filterable placeholder="明确选择目标，不能从题干推测" aria-label="目标接车进路"><el-option v-for="item in routes" :key="item.id" :value="item.id" :label="`${item.button_sequence.join(' → ')}（${item.id}）`" /></el-select></el-form-item>
        <p class="op-help">交卷时须保持指定进路锁闭及正常允许信号。替代进路必须具有相同始端、终端和规定显示。</p>
        <el-checkbox v-model="form.wrong_signal_cap">将错误进路信号开放列为关键操作不合格，本题最高59分</el-checkbox>
        <p class="op-help">未启用时，该错误扣操作规范20分。临时误选清除扣2分；错误进路锁闭但未开放信号扣10分；同一错误不重复扣分。普通无效请求扣5分，未完成核心任务最高59分。</p>
        <p class="op-help">本正常接车模板不允许引导、人工解锁、区故解或事故辅助处理；对设备进行题目不要求的实际改变也会评价。题目若要求这些操作，请使用人工批阅。</p>
        <el-checkbox v-model="form.confirmed">我已核对目标、结束条件和本模板评分规则，确认本题适用</el-checkbox>
      </template>
      <div v-if="!locked" class="op-actions"><el-button :loading="busy" @click="save">保存评价设置</el-button><span class="op-help">须保存后再发布；考试发布时再次检查目标可完成。</span></div>
      <p v-else class="op-help">当前版本只读。需要调整时，请先修改题设建立新草稿，再配置评价。</p>
    </el-form>
  </section>
</template>
<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { getOperationStation } from '@/api/operations'
import { getAssessmentConfig, saveAssessmentConfig } from '@/api/operationAssessment'
const props = defineProps({ questionId: {type:Number,required:true}, locked:Boolean })
const emit=defineEmits(['dirty'])
const form = reactive({revision:0,enabled:false,route_ids:[],wrong_signal_cap:false,confirmed:false})
const station = ref(null), busy = ref(false), ready = ref(false), notice = ref(''), failed = ref(false)
const saved=ref('')
watch(()=>JSON.stringify(form),value=>emit('dirty',ready.value && value!==saved.value))
const routes = computed(() => { const entries = new Set((station.value?.signals || []).filter(s=>s.entry).map(s=>s.name)); return (station.value?.routes || []).filter(r=>r.kind==='train' && entries.has(r.signal) && !r.subroutes?.length) })
let serial=0
watch(()=>props.questionId,async id=>{const token=++serial;ready.value=false;emit('dirty',false);try{const [config,pkg]=await Promise.all([getAssessmentConfig(id),getOperationStation()]);if(token!==serial)return;for(const key of Object.keys(form))form[key]=config[key];station.value=pkg;saved.value=JSON.stringify(form);ready.value=true}catch(e){notice.value=e.response?.data?.detail || '评价设置加载失败';failed.value=true}},{immediate:true})
async function save(){busy.value=true;notice.value='';try{const body=Object.fromEntries(Object.keys(form).map(k=>[k,form[k]]));const result=await saveAssessmentConfig(props.questionId,body);for(const key of Object.keys(form))form[key]=result[key];saved.value=JSON.stringify(form);emit('dirty',false);failed.value=false;notice.value='评价设置已保存。'}catch(e){failed.value=true;notice.value=e.response?.data?.detail || '保存失败，请保留当前选择并重试'}finally{busy.value=false}}
</script>
<style scoped>
.el-checkbox{height:auto;white-space:normal;align-items:flex-start;margin:14px 0}.el-checkbox :deep(.el-checkbox__label){white-space:normal;line-height:1.7}.el-select{width:100%}.el-form{margin-top:20px}.op-help{line-height:1.8}
</style>
