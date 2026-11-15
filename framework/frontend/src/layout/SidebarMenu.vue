<template>
  <div class="sidebar">
    <div class="sidebar-caption"><span class="caption-mark"></span> 实训平台 </div>
    <nav aria-label="主导航" class="sidebar-navigation">
      <section v-for="group in groups" :key="group.title" class="nav-group">
        <h2>{{ group.title }}</h2>
        <router-link v-for="item in group.items" :key="item.path" :to="item.path" :class="['nav-item', { active: activePath === item.path }]" :aria-current="activePath === item.path ? 'page' : undefined" @click="$emit('navigate')">
          <el-icon><component :is="item.icon" /></el-icon><span>{{ item.title }}</span><span v-if="item.number" class="nav-number">{{ item.number }}</span><span v-if="activePath === item.path" class="nav-active-dot"></span>
        </router-link>
      </section>
    </nav>
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
const learningPath = computed(() => route.path.startsWith('/student/modules') || route.path.startsWith('/student/interlocking-exam') || route.path === '/teacher/lab-topics' ? '/student/lab-topics' : route.path)
const activePath = computed(() => groups.value.flatMap(group => group.items)
  .filter(item => learningPath.value === item.path || learningPath.value.startsWith(item.path + '/'))
  .sort((a, b) => b.path.length - a.path.length)[0]?.path)
</script>
