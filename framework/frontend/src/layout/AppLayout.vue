<template>
  <div class="app-layout">
    <a class="skip-link" href="#main-content">跳转到主要内容</a>
    <header class="university-header">
      <router-link to="/" class="university-brand" aria-label="返回实训首页"><img src="/brand/swjtu-logo.png" alt="西南交通大学 Southwest Jiaotong University" /></router-link>
      <span class="university-divider"></span>
      <div class="platform-brand"><strong>铁路联锁实训</strong><span>RAILWAY INTERLOCKING LAB</span></div>
      <div class="university-links"><a href="https://www.swjtu.edu.cn/xxgk/xswh.htm" target="_blank" rel="noopener noreferrer">交大文化 <span>↗</span></a><a href="https://www.swjtu.edu.cn/" target="_blank" rel="noopener noreferrer">学校官网 <span>↗</span></a></div>
    </header>
    <div class="app-body">
      <aside class="layout-aside"><SidebarMenu /></aside>
      <div class="workspace">
        <HeaderBar @toggle-menu="mobileMenu = true" />
        <main id="main-content" class="layout-main" tabindex="-1">
          <CampusBanner v-if="showBanner" />
          <router-view />
        </main>
        <footer class="workspace-footer"><span>SRTP <i>·</i> 铁路计算机联锁仿真实训系统</span><a href="https://www.swjtu.edu.cn/xxgk/xswh.htm" target="_blank" rel="noopener noreferrer">视觉参考：西南交通大学</a></footer>
      </div>
    </div>
    <el-drawer v-model="mobileMenu" title="功能导航" direction="ltr" size="264px" class="navigation-drawer"><SidebarMenu @navigate="mobileMenu = false" /></el-drawer>
  </div>
</template>
<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import HeaderBar from './HeaderBar.vue'
import SidebarMenu from './SidebarMenu.vue'
import CampusBanner from '@/components/CampusBanner.vue'
const route = useRoute(), mobileMenu = ref(false)
const showBanner = computed(() => ['/admin', '/student/dashboard', '/student/lobby', '/teacher/dashboard'].includes(route.path))
watch(() => route.path, () => { mobileMenu.value = false })
</script>
