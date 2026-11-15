<template><div class="standard-preview" role="img" aria-label="标准站示意图"><ReferenceStationDiagram v-if="station" :station="station" :snapshot="null" :selected="[]" aria-hidden="true" inert/><p v-else>{{ error || '正在加载标准站…' }}</p></div></template>
<script setup>
import {onMounted,ref} from 'vue'
import request from '@/utils/request'
import ReferenceStationDiagram from '@/features/simulationConsole/ReferenceStationDiagram.vue'
const station=ref(null),error=ref('')
onMounted(async()=>{try{station.value=await request.get('/simulation-console/station')}catch{error.value='标准站加载失败，请重新打开预览。'}})
</script>
<style scoped>.standard-preview{background:#000;border-radius:6px;overflow:hidden;margin:20px 0;min-height:140px}.standard-preview :deep(.reference-diagram){width:100%;height:auto;min-width:0;min-height:0;pointer-events:none}.standard-preview p{padding:20px;color:#c0c0c0;font-size:13px}</style>
