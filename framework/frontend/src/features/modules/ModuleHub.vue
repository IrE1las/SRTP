<template>
  <main class="modules-page" v-loading="loading">
    <header class="module-heading"><div><span class="eyebrow">INTERLOCKING LAB · 2.0</span><h1>{{ current?.title || '三模块实验中心' }}</h1><p>{{ current?.description || '按实验目标进入对应站场，在操作与复盘中理解联锁。' }}</p></div><router-link v-if="current" to="/student/modules">返回实验中心</router-link></header>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <section v-if="!current" class="module-grid">
      <router-link v-for="(item, i) in modules" :key="item.id" :to="`/student/modules/${item.id}`" class="module-card">
        <span class="card-number">0{{ i + 1 }}</span><span class="status-tag">{{ statusText(item.status) }}</span>
        <h2>{{ item.title }}</h2><p>{{ item.description }}</p><div class="card-bottom">实验 {{ item.experiments.map(e => e.id).join(' · ') }}<span>查看模块 →</span></div>
      </router-link>
    </section>
    <template v-else-if="current.id === 'one'">
      <div class="module-note">一号车站 · 动态操作。实验一按小题初始化独立场景，连续动作在同一作答内完成。</div>
      <section class="module-grid experiments">
        <article v-for="exp in current.experiments" :key="exp.id" class="module-card"><span class="card-number">0{{ exp.id }}</span><h2>实验{{ ['','一','二','三','四'][exp.id] }}</h2><p>{{ exp.id === 1 ? '道岔单独操作、调车进路、变通进路与接车联锁。第 1—4 题及第 5 题（1）—（4）可作答。' : '实验规则与题目待后续设计。' }}</p><router-link v-if="exp.id === 1" class="primary-link" to="/student/modules/one/experiment-1">进入实验一 →</router-link><span v-else class="status-tag">规划中</span></article>
      </section>
      <router-link class="secondary-link" to="/student/simulation-console">自由仿真 · 进入探索操作台 →</router-link>
    </template>
    <template v-else-if="current.id === 'two'">
      <div class="module-note">二号车站 · 原图站场。下方仅展示已有实验五、六的联锁表资源，沿用原作答和批阅流程。</div>
      <section class="module-grid experiments"><article v-for="n in [5,6]" :key="n" class="module-card"><span class="card-number">0{{ n }}</span><h2>实验{{ n === 5 ? '五' : '六' }} · 二号车站</h2><p>{{ n === 5 ? '联锁关系与联锁表填写' : '调车联锁表与进路核对' }}</p><ul class="resource-list"><li v-for="q in resources.filter(q => q.topic === n)" :key="q.key"><router-link :to="{path:'/student/lab-topics',query:{q:q.key}}">{{ q.title }} →</router-link></li></ul><p v-if="!resources.some(q => q.topic === n)">尚无已核实的可用题目，请先初始化或核对二号车站教学资料。</p></article></section>
      <details class="reference-photo"><summary>查看二号车站原图</summary><img :src="originalPhoto" alt="二号车站原始站场图" /></details>
    </template>
    <template v-else>
      <div class="module-note">规划中 · 当前仅展示实验目标，尚未开放作答和评分。</div>
      <section class="module-grid experiments"><article class="module-card"><span class="card-number">07</span><h2>实验七 · 半自动闭塞</h2><p>理解区间许可、闭塞办理及复原条件。题设、设备状态与判题规则待设计。</p><span class="status-tag">规划中</span></article><article class="module-card"><span class="card-number">08</span><h2>实验八 · ZPW-2000</h2><p>学习区间信号与低频信息。实验资料、动态场景与教师评分依据待完善。</p><span class="status-tag">规划中</span></article></section>
    </template>
  </main>
</template>
<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { getModules } from './api'
import { getLabQuestions, getLabQuestion } from '@/api/labTopics'
import originalPhoto from '../../../../../pictures/原始图.jpg'
import './modules.css'
const route = useRoute(), modules = ref([]), resources = ref([]), loading = ref(true), error = ref('')
const current = computed(() => modules.value.find(m => m.id === route.params.moduleId))
function statusText(s) { return {active:'可进入',resources:'已有作答资源',planned:'规划中'}[s] || s }
onMounted(async () => {
  try {
    modules.value = await getModules()
    const candidates = (await getLabQuestions()).filter(q => [5,6].includes(q.topic))
    const verified = await Promise.all(candidates.map(q => getLabQuestion(q.key)))
    resources.value = verified.filter(q => q.station_key === 'original-photo-station' && [5,6].includes(q.topic))
  } catch (e) { error.value = e.response?.data?.detail || '实验资源加载失败，请刷新重试。' }
  finally { loading.value = false }
})
</script>
