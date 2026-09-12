<template>
  <div class="lobby-page">
    <div class="section-title-row"><div><span class="section-overline">PRACTICE CENTER</span><h2>选择你的实训任务</h2></div><span class="lobby-subtitle">循序渐进，知行合一</span></div>
    <router-link class="report-entry" to="/student/lab-topics"><div><strong>车站与区间控制 · 实验专题</strong><p>对应实验一至八，围绕原始站场完成读图、联锁表填写、现象分析与区间闭塞练习。</p></div><span>进入专题 →</span></router-link>
    <div class="lobby-controls">
      <div class="lobby-tabs" role="tablist" aria-label="练习分类"><button id="classic-tab" :class="{ active: activeTab === 'classic' }" role="tab" :aria-selected="activeTab === 'classic'" aria-controls="lobby-panel" @click="activeTab = 'classic'">经典专项 <span>04</span></button><button id="published-tab" :class="{ active: activeTab === 'published' }" role="tab" :aria-selected="activeTab === 'published'" aria-controls="lobby-panel" @click="activeTab = 'published'">教学练习 <span>{{ store.lobbyExercises.length }}</span></button></div>
      <el-input v-model="query" :prefix-icon="Search" placeholder="搜索练习名称或专题" clearable class="lobby-search" aria-label="搜索练习" />
    </div>
    <div id="lobby-panel" role="tabpanel" :aria-labelledby="activeTab === 'classic' ? 'classic-tab' : 'published-tab'">
      <div v-if="activeTab === 'classic'" class="topic-grid">
        <router-link v-for="exam in filteredTopics" :key="exam.index" :to="exam.route" class="topic-card">
          <div class="topic-card-top"><span class="topic-category">{{ exam.topic }}专题</span><span class="topic-index">{{ exam.index }}</span></div>
          <div class="route-art" aria-hidden="true"><span></span><i></i><span></span><b></b></div>
          <h3>{{ exam.subtitle }}</h3><p class="topic-description">{{ descriptions[exam.index] }}</p>
          <div class="topic-card-bottom"><span><el-icon><Clock /></el-icon> 不限时 · 自主作答</span><span class="card-action">开始练习 <el-icon><Right /></el-icon></span></div>
        </router-link>
        <el-empty v-if="!filteredTopics.length" description="没有找到匹配的专题" />
      </div>
      <div v-else v-loading="store.loading" class="topic-grid">
        <router-link v-for="exercise in filteredPublished" :key="exercise.id" :to="'/student/exercises/' + exercise.id" class="topic-card published-card">
          <div class="topic-card-top"><span class="topic-category">教学练习</span><el-tag size="small">{{ difficultyText(exercise.difficulty) }}</el-tag></div>
          <h3>{{ exercise.title }}</h3><p class="topic-description">{{ exercise.description || '进入站场，按照题目要求完成进路操作。' }}</p>
          <div class="topic-card-bottom"><span><el-icon><Clock /></el-icon> {{ exercise.time_limit }} 秒</span><span class="card-action">开始练习 <el-icon><Right /></el-icon></span></div>
        </router-link>
        <el-empty v-if="!store.loading && !filteredPublished.length" :description="query ? '没有找到匹配的练习' : '暂无已发布的教学练习'" />
      </div>
    </div>
    <div class="learning-tip"><el-icon><Reading /></el-icon><div><strong>让每一道错题都有收获</strong><p>自主选择设备并提交检验，查看漏选、多选与错位，再结合错误解析梳理原因。</p></div></div>
  </div>
</template>
<script setup>
import { computed, onMounted, ref } from 'vue'
import { Clock, Reading, Right, Search } from '@element-plus/icons-vue'
import { useExerciseStore } from '@/store/exercise'
import { difficultyText } from '@/utils/statusText'
import { exams } from '@/domain/classicStation'
const store = useExerciseStore(), activeTab = ref('classic'), query = ref('')
const descriptions = { '01': '在完整站场上选择进路按钮、设置道岔，梳理敌对信号与检查区段。', '02': '结合接车任务，理解防护道岔的作用，检查进路的安全条件。', '03': '结合接车任务辨析带动道岔，理清各项联锁条件之间的关系。', '04': '23/25、5/7 道岔处于定位是题设环境；各设备仍可自由加入答案。' }
const filteredTopics = computed(() => Object.values(exams).filter(exam => (exam.title + exam.topic).toLowerCase().includes(query.value.trim().toLowerCase())))
const filteredPublished = computed(() => store.lobbyExercises.filter(exercise => (exercise.title + (exercise.description || '')).toLowerCase().includes(query.value.trim().toLowerCase())))
onMounted(() => store.loadLobby())
</script>
<style scoped>
.report-entry { display:flex; justify-content:space-between; align-items:center; gap:20px; margin-top:23px; padding:22px 25px; background:#eaf4fb; border:1px solid #bad7e9; border-radius:9px; color:#286382; }.report-entry strong{font-size:var(--ui-text-md)}.report-entry p{font-size:var(--ui-text-base);line-height:1.8;color:#68879d;margin:10px 0 0}.report-entry>span{font-size:var(--ui-text-base);white-space:nowrap}@media(max-width:600px){.report-entry{align-items:flex-start;flex-direction:column;padding:20px}}
.lobby-subtitle { color: #586f82; font-size: var(--ui-text-meta); }
.lobby-controls { display: flex; align-items: center; justify-content: space-between; gap: 20px; margin: 23px 0; border-bottom: 1px solid #e2e8ef; padding-bottom: 15px; }
.lobby-tabs { display: flex; gap: 26px; }.lobby-tabs button { background: none; border: 0; color: #586f82; padding: 8px 0; font-size: var(--ui-text-base); }.lobby-tabs button.active { color: #0075b7; font-weight: 600; }.lobby-tabs button span { font: var(--ui-text-sm) Georgia, serif; margin-left: 6px; background: #e8eef4; border-radius: 4px; padding: 3px 6px; }.lobby-tabs button.active span { background: #e1eff8; }
.lobby-search { width: 235px; }.lobby-search :deep(.el-input__inner) { font-size: var(--ui-text-meta); }
.topic-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px; }
.topic-grid > .el-empty { grid-column: 1/-1; }
.topic-card { color: var(--swjtu-ink); background: white; border: 1px solid #e2e9f0; padding: 25px 27px 21px; border-radius: 9px; transition: border-color .2s, box-shadow .2s; }
.topic-card:hover { border-color: #a8c9df; box-shadow: 0 5px 18px #183e6908; }
.topic-card-top { display: flex; justify-content: space-between; align-items: center; }.topic-category { color: #587e9a; font-size: var(--ui-text-meta); letter-spacing: .6px; }.topic-index { font: 31px Georgia, serif; color: #bccddc; }
.topic-card h3 { font-size: var(--ui-text-heading); font-weight: 600; margin: 13px 0 12px; letter-spacing: .5px; }
.topic-description { color: #586f82; font-size: var(--ui-text-base); line-height: 1.9; margin: 0 0 24px; min-height: 46px; }
.route-art { position: relative; height: 27px; margin-top: 13px; width: 122px; display: flex; align-items: center; }
.route-art span { width: 7px; height: 7px; border: 2px solid #abc6d9; border-radius: 50%; }.route-art i { flex: 1; height: 2px; background: #bfd3e2; }.route-art b { position: absolute; width: 34px; height: 17px; left: 53px; top: 13px; border-top: 2px solid #bfd3e2; transform: skewY(-28deg); transform-origin: top left; }
.topic-card-bottom { display: flex; justify-content: space-between; align-items: center; gap: 12px; border-top: 1px solid #edf1f5; padding-top: 17px; }.topic-card-bottom > span { color: #586f82; font-size: var(--ui-text-sm); display: flex; align-items: center; gap: 6px; }.topic-card-bottom .card-action { gap: 18px; font-size: var(--ui-text-base); color: #0075b7; }
.published-card h3 { margin-top: 26px; }
.learning-tip { margin-top: 25px; display: flex; align-items: center; gap: 17px; background: #edf3f8; padding: 23px 26px; border-radius: 8px; }
.learning-tip > .el-icon { font-size: 28px; color: #586f82; }.learning-tip strong { font-size: var(--ui-text-base); font-weight: 500; color: #52728a; }.learning-tip p { color: #586f82; font-size: var(--ui-text-meta); margin: 8px 0 0; line-height: 1.8; }
@media (max-width: 600px) { .lobby-controls { flex-wrap: wrap; gap: 10px; }.lobby-search { width: 100%; }.topic-grid { grid-template-columns: 1fr; gap: 15px; }.topic-card { padding: 20px; }.topic-card h3 { font-size: var(--ui-text-heading); }.lobby-subtitle { display: none; }.learning-tip { padding: 20px; align-items: flex-start; flex-wrap: wrap; }.learning-tip > div { flex: 1; }.topic-description { min-height: 0; } }
</style>
