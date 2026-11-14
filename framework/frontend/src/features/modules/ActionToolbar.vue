<template>
  <div class="action-toolbar">
    <fieldset :disabled="disabled"><legend>道岔单独操作</legend><label>道岔组<select v-model="group"><option v-for="g in groups" :key="g" :value="g">{{ g }}</option></select></label><div class="control-buttons"><button v-for="[type,label] in switchCommands" :key="type" @click="emit('command',type,group,{})">{{ label }}</button></div></fieldset>
    <fieldset v-if="environment.length" :disabled="disabled"><legend>题目环境工具</legend><label>设备<select v-model="environmentTarget"><option v-for="e in environment" :key="e.target" :value="e.target">{{ e.target }}</option></select></label><div class="control-buttons"><button v-for="kind in environmentKinds" :key="kind" @click="environmentCommand(kind)">{{ environmentLabels[kind] }}</button></div><small>仅限本题设备与指定操作阶段，设置过程计入记录。</small></fieldset>
    <fieldset :disabled="disabled"><legend>进路操作</legend><label>已办进路<select v-model="instance"><option value="">请选择</option><option v-for="r in activeRoutes" :key="r.id" :value="r.id">{{ r.signal }} · {{ r.route_id }} 号</option></select></label><div class="control-buttons"><button @click="emit('command','CANCEL_ROUTE',instance,{})">总取消</button><button @click="emit('command','REPEAT_OPEN_SIGNAL',instance,{})">重复开放</button><button @click="emit('command','CLEAR_SELECTION','',{})">清除临时按钮</button></div></fieldset>
    <details><summary>全部进路按钮 · 键盘操作</summary><fieldset :disabled="disabled" class="button-inventory"><button v-for="b in station.buttons" :key="b.name" @click="emit('command','PRESS_BUTTON',b.name,{})">{{ b.name }}</button></fieldset></details>
  </div>
</template>
<script setup>
import { computed, ref, watch } from 'vue'
const props = defineProps({station:Object,snapshot:Object,environment:{type:Array,default:()=>[]},disabled:Boolean,selectedGroup:String})
const emit = defineEmits(['command'])
const group=ref('5/7'),instance=ref(''),environmentTarget=ref('')
const groups=computed(()=>[...new Set(props.station.switches.map(s=>[s.id,s.mate].filter((x,i,a)=>x&&a.indexOf(x)===i).sort((a,b)=>Number(a)-Number(b)).join('/')))])
const switchCommands=[['SWITCH_TOTAL_NORMAL','总定'],['SWITCH_TOTAL_REVERSE','总反'],['SWITCH_SINGLE_LOCK','单锁'],['SWITCH_SINGLE_UNLOCK','单解'],['SWITCH_SEAL','封闭'],['SWITCH_UNSEAL','解封']]
const activeRoutes=computed(()=>(props.snapshot?.routes||[]).filter(r=>!['released','cancelled'].includes(r.status)))
const environmentKinds=computed(()=>props.environment.find(e=>e.target===environmentTarget.value)?.kinds||[])
const environmentLabels={vehicle:'设置车列占用',fault:'设置故障占用',clear:'恢复区段空闲',indication:'设置失表示',restore_indication:'恢复表示'}
watch(()=>props.environment, e=>environmentTarget.value=e[0]?.target||'',{immediate:true})
watch(()=>props.selectedGroup, value=>{if(value)group.value=value})
watch(activeRoutes, value=>{if(!value.some(r=>r.id===instance.value))instance.value=value[0]?.id||''})
function environmentCommand(kind){
  const type={clear:'CLEAR_SECTION_OCCUPANCY',indication:'SET_SWITCH_INDICATION',restore_indication:'RESTORE_SWITCH_INDICATION'}[kind]||'SET_SECTION_OCCUPANCY'
  emit('command',type,environmentTarget.value,['vehicle','fault'].includes(kind)?{kind}:{})
}
</script>
