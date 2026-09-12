<template>
  <div class="sidebar">
    <div class="sidebar-caption"><span class="caption-mark"></span> 知行 · 实训平台 <span class="version-tag">SRTP</span></div>
    <nav aria-label="主导航" class="sidebar-navigation">
      <section v-for="group in groups" :key="group.title" class="nav-group">
        <h2>{{ group.title }}</h2>
        <router-link v-for="item in group.items" :key="item.path" :to="item.path" :class="['nav-item', { active: activePath === item.path }]" :aria-current="activePath === item.path ? 'page' : undefined" @click="$emit('navigate')">
          <el-icon><component :is="item.icon" /></el-icon><span>{{ item.title }}</span><span v-if="item.number" class="nav-number">{{ item.number }}</span><span v-if="activePath === item.path" class="nav-active-dot"></span>
        </router-link>
      </section>
    </nav>
    <div class="sidebar-motto"><span class="motto-line"></span><p>精勤求学　敦笃励志<br />果毅力行　忠恕任事</p><span>知其然，更知其所以然</span></div>
  </div>
</template>
<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useUserStore } from '@/store/user'
import { navigationGroups } from '@/ui/navigation'
defineEmits(['navigate'])
const route = useRoute(), userStore = useUserStore()
const groups = computed(() => navigationGroups(userStore.role))
const activePath = computed(() => groups.value.flatMap(group => group.items)
  .filter(item => route.path === item.path || route.path.startsWith(item.path + '/'))
  .sort((a, b) => b.path.length - a.path.length)[0]?.path)
</script>
