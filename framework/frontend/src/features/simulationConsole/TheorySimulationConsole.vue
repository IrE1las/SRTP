<template><SimulationConsole :key="questionKey" :client="client" embedded /></template>
<script setup>
import { computed } from 'vue'
import SimulationConsole from './SimulationConsole.vue'
import { createTheoryConsoleClient } from '@/api/theoryConsole'
const props=defineProps({questionKey:{type:String,required:true}})
const client=computed(()=>({...createTheoryConsoleClient(props.questionKey),storageKey:`theory-${props.questionKey}`}))
</script>
