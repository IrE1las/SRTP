<template>
  <section class="campus-banner">
    <img class="campus-banner-photo" src="/brand/swjtu-campus.png" alt="" />
    <div class="campus-banner-content">
      <p class="banner-kicker"><span></span> SOUTHWEST JIAOTONG UNIVERSITY</p>
      <h1><span>{{ title.split('，')[0] }}<span class="banner-comma">，</span></span><span>{{ title.split('，')[1] }}</span></h1>
      <p class="banner-description">{{ description }}</p>
      <router-link v-if="userStore.role !== 'teacher'" to="/student/interlocking-exam" class="banner-link">进入专项实训 <el-icon><Right /></el-icon></router-link>
      <router-link v-else to="/teacher/exercises" class="banner-link">管理教学练习 <el-icon><Right /></el-icon></router-link>
    </div>
    <div class="banner-seal" aria-hidden="true"><span>竢实扬华</span><span>自强不息</span></div>
  </section>
</template>
<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { Right } from '@element-plus/icons-vue'
import { useUserStore } from '@/store/user'
const route = useRoute(), userStore = useUserStore()
const title = computed(() => route.path === '/student/lobby' ? '在实践中求知，在思考中精进' : route.path.startsWith('/teacher') ? '传道授业，知行相长' : '以知促行，学以致用')
const description = computed(() => route.path === '/student/lobby' ? '从一条进路开始，理解每一次操作背后的联锁逻辑。' : route.path.startsWith('/teacher') ? '关注学习过程，让每一次反馈都成为成长的起点。' : '铁路联锁实训 · 从自主作答到错误定位，让每一次练习都有收获。')
</script>
