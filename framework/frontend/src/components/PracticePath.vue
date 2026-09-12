<template>
  <section class="practice-path">
    <div class="section-title-row"><div><span class="section-overline">LEARNING PATH</span><h2>从理解到实践</h2></div><router-link to="/student/lobby">全部练习 <el-icon><Right /></el-icon></router-link></div>
    <div class="practice-path-grid">
      <router-link v-for="item in topics" :key="item.path" :to="item.path" class="path-card">
        <div class="path-card-top"><el-icon><component :is="item.icon" /></el-icon><span>{{ item.number }}</span></div>
        <h3>{{ item.title }}</h3><p>{{ descriptions[item.number] }}</p>
        <span class="path-card-link">开始实训 <el-icon><Right /></el-icon></span>
      </router-link>
    </div>
  </section>
</template>
<script setup>
import { Right } from '@element-plus/icons-vue'
import { navigationGroups } from '@/ui/navigation'
const topics = navigationGroups('student')[1].items
const descriptions = { '01': '读懂进路，建立联锁逻辑', '02': '理解防护，辨析安全条件', '03': '关注联动，梳理道岔关系', '04': '结合题设，判断检查区段' }
</script>
