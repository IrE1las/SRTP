<template>
  <main class="experiment-center">
    <header class="center-heading"><div><h1>实验专题</h1></div><router-link to="/student/history">实验学习记录 →</router-link></header>
    <nav class="center-tabs" aria-label="实验学习分类"><button v-for="item in tabs" :key="item.id" :class="{ active: view === item.id }" :aria-pressed="view === item.id" @click="selectView(item.id)">{{ item.title }}</button></nav>
    <section v-if="view === 'overview'" class="center-grid" aria-label="选择实验方式">
      <button v-for="item in categories" :key="item.id" class="center-card" @click="selectView(item.id)"><span class="card-number">{{ item.number }}</span><h2>{{ item.title }}</h2><span class="card-action">进入{{ item.title }} <span aria-hidden="true">→</span></span></button>
    </section>
    <LabTopics v-else-if="view === 'reports'" embedded />
    <section v-else-if="view === 'classic'" class="center-grid classic-grid" aria-label="图形专项">
      <router-link v-for="exam in exams" :key="exam.index" class="center-card" :to="exam.route"><span class="card-number">{{ exam.index }}</span><span class="topic-tag">{{ exam.topic }}</span><h2>{{ exam.subtitle }}</h2><span class="card-action">进入图形作答 <span aria-hidden="true">→</span></span></router-link>
    </section>
    <section v-else class="center-grid" aria-label="动态操作实验">
      <router-link class="center-card" to="/student/modules/one/experiment-1"><span class="card-number">01</span><span class="topic-tag">一号车站</span><h2>进路与道岔操作</h2><span class="card-action">进入实验一 <span aria-hidden="true">→</span></span></router-link>
      <router-link class="center-card" to="/student/modules/two"><span class="card-number">02</span><span class="topic-tag">二号车站</span><h2>联锁表实验</h2><span class="card-action">进入联锁表实验 <span aria-hidden="true">→</span></span></router-link>
      <router-link class="center-card secondary-card" to="/student/modules"><span class="card-number">…</span><h2>实验目录</h2><span class="card-action">查看完整目录 <span aria-hidden="true">→</span></span></router-link>
    </section>
  </main>
</template>
<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import LabTopics from '@/views/student/LabTopics.vue'
import { exams } from '@/domain/classicStation'
const route = useRoute(), router = useRouter()
const categories = [
  { id: 'reports', number: '01', title: '专题作答', description: '实验一至八，读图填写、记录现象、分析原因，提交后查看反馈与教师评阅。' },
  { id: 'classic', number: '02', title: '图形专项', description: '在完整站场上选择设备，练习基础进路、防护道岔、带动道岔和条件区段。' },
  { id: 'dynamic', number: '03', title: '动态操作', description: '在独立场景中连续操作，观察联锁状态，查看错误点并回放实验过程。' },
]
const tabs = [{ id: 'overview', title: '全部实验' }, ...categories]
const view = computed(() => tabs.some(item => item.id === route.query.view) ? route.query.view : route.query.q ? 'reports' : 'overview')
function selectView(id) { router.push({ path: route.path, query: id === 'overview' ? {} : { view: id } }) }
</script>
<style scoped>
.experiment-center{max-width:1320px;margin:auto;color:#183b58}.center-heading{display:flex;justify-content:space-between;align-items:center;gap:16px;margin-bottom:16px}.eyebrow{font-size:10px;letter-spacing:1.5px;color:#0075b7}.center-heading h1{font-size:27px;margin:5px 0 0;font-weight:600}.center-heading a{font-size:13px;color:#0075b7}.center-tabs{display:flex;gap:8px;flex-wrap:wrap;border-bottom:1px solid #dfe8ef;padding-bottom:12px;margin-bottom:18px}.center-tabs button{padding:9px 18px;border:1px solid transparent;border-radius:6px;background:transparent;color:#617a8c;font:inherit;font-size:14px;cursor:pointer}.center-tabs button.active{background:#e6f1f8;border-color:#c8dfed;color:#0075b7}.center-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}.center-card{display:block;position:relative;text-align:left;background:#fff;border:1px solid #dce6ef;border-top:3px solid #c6aa70;border-radius:9px;padding:21px;color:inherit;font:inherit;cursor:pointer;min-width:0}.center-card:hover{border-color:#8ab1ca}.card-number{font:30px Georgia,serif;color:#aec3d1}.center-card h2{font-size:19px;font-weight:500;margin:12px 0 18px;line-height:1.6}.center-card p{font-size:13px;line-height:1.85;color:#6d8292;margin:0 0 20px}.card-action{display:flex;justify-content:space-between;border-top:1px solid #e9eff4;padding-top:13px;color:#0075b7;font-size:13px}.topic-tag{float:right;font-size:12px;color:#738897;padding-top:8px}.classic-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.secondary-card{border-top-color:#cad8e3}.experiment-center :is(button,a):focus-visible{outline:3px solid #0075b7;outline-offset:3px}@media(max-width:1000px){.center-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:600px){.center-grid{grid-template-columns:1fr;gap:12px}.center-heading{align-items:flex-start}.center-heading h1{font-size:23px}.center-tabs{gap:3px}.center-tabs button{padding:8px 12px;font-size:13px}.center-card{padding:18px}.center-heading a{font-size:12px}}
</style>
