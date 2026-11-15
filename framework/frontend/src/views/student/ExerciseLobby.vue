<template>
  <main class="lobby-page"><header class="section-title-row"><h1>学习与练习</h1></header><StudyLinks/><section class="published-exercises"><h2>教师发布的教学练习</h2><el-input v-model="query" placeholder="搜索练习" aria-label="搜索教师练习" clearable/><el-empty v-if="!filtered.length" description="暂无符合条件的教学练习"/><article v-for="exercise in filtered" :key="exercise.id"><h3>{{ exercise.title }}</h3><p>{{ exercise.description }}</p><router-link :to="`/student/exercises/${exercise.id}`">进入练习</router-link></article></section></main>
</template>
<script setup>
import {computed,onMounted,ref} from 'vue'
import {useExerciseStore} from '@/store/exercise'
import StudyLinks from '@/components/StudyLinks.vue'
const store=useExerciseStore(),query=ref('')
const filtered=computed(()=>store.lobbyExercises.filter(q=>(q.title+' '+(q.description||'')).includes(query.value.trim())))
onMounted(()=>store.loadLobby())
</script>
<style scoped>.published-exercises{margin-top:30px}.published-exercises h2{font-size:20px;font-weight:500}.published-exercises>.el-input{max-width:400px}.published-exercises article{background:white;border:1px solid #e0e7ef;padding:22px;margin-top:15px;border-radius:8px}.published-exercises h3{font-size:18px;font-weight:500}.published-exercises p{color:#708094;line-height:1.8}</style>
