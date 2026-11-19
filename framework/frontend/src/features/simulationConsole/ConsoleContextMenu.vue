<template>
  <div ref="menu" class="console-context-menu" :style="position" role="menu" :aria-label="title" @keydown="onKey" @contextmenu.prevent>
    <div class="context-title">{{ title }}</div>
    <template v-for="(item, index) in items" :key="item.key || index">
      <hr v-if="item.separator" role="separator" />
      <button v-else role="menuitem" :disabled="item.disabled" :title="item.reason" @click="$emit('choose', item)">{{ item.label }}</button>
    </template>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
const props = defineProps({ title: String, items: Array, x: Number, y: Number, width: Number, height: Number, minX: {type:Number,default:6}, minY: {type:Number,default:6} })
const emit = defineEmits(['choose', 'close'])
const menu=ref(null), left=ref(props.x), top=ref(props.y)
const position=computed(()=>({left:`${left.value}px`,top:`${top.value}px`,maxHeight:`${Math.max(60,props.height-props.minY-6)}px`}))
onMounted(async()=>{await nextTick();left.value=Math.max(props.minX,Math.min(props.x,props.width-menu.value.offsetWidth-6));top.value=Math.max(props.minY,Math.min(props.y,props.height-menu.value.offsetHeight-6));menu.value.querySelector('button:not(:disabled)')?.focus({preventScroll:true})})
function onKey(event){
  if(event.key==='Escape'){emit('close');event.stopPropagation();return}
  if(!['ArrowDown','ArrowUp','Home','End'].includes(event.key))return
  event.preventDefault()
  const buttons=[...menu.value.querySelectorAll('button:not(:disabled)')], index=buttons.indexOf(document.activeElement)
  const next=event.key==='Home'?0:event.key==='End'?buttons.length-1:(index+(event.key==='ArrowDown'?1:-1)+buttons.length)%buttons.length
  buttons[next]?.focus()
}
</script>

<style scoped>
.console-context-menu{position:absolute;z-index:12;min-width:206px;max-width:min(460px,calc(100% - 12px));overflow:auto;box-sizing:border-box;padding:3px;background:#c0c0c0;color:#000;border:2px outset #eee;box-shadow:3px 3px 0 #0009;font:14px 'Microsoft YaHei',SimSun,sans-serif}
.context-title{padding:5px 12px 7px;color:#333;font-size:12px;border-bottom:1px solid #888;margin-bottom:3px}
button{display:block;box-sizing:border-box;width:100%;padding:7px 18px;text-align:left;border:0;background:transparent;color:inherit;font:inherit;cursor:pointer}
button:hover:not(:disabled),button:focus-visible{background:#000080;color:#fff;outline:0}button:disabled{color:#737373;cursor:default;text-shadow:1px 1px #eee}
hr{border:0;border-top:1px solid #808080;border-bottom:1px solid #eee;margin:4px 2px}
</style>
