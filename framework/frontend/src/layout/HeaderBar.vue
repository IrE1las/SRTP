<template>
  <div class="workspace-header">
    <div class="breadcrumb"><button class="mobile-menu-button icon-button" aria-label="打开导航菜单" @click="$emit('toggle-menu')"><el-icon><Expand /></el-icon></button><el-icon class="breadcrumb-home"><HomeFilled /></el-icon><span class="breadcrumb-root">实训平台</span><span class="breadcrumb-divider">/</span><strong>{{ currentTitle }}</strong></div>
    <div class="header-tools">
      <button class="page-search" @click="searchOpen = true"><el-icon><Search /></el-icon><span>查找页面</span></button>
      <span class="header-tool-divider"></span>
      <el-dropdown trigger="click" @command="handleCommand">
        <button class="user-menu"><span class="user-avatar">{{ displayName.slice(0, 1).toUpperCase() }}</span><span class="user-details"><strong>{{ displayName }}</strong><small>{{ roleLabel }}</small></span><el-icon><ArrowDown /></el-icon></button>
        <template #dropdown><el-dropdown-menu><el-dropdown-item command="logout">退出登录</el-dropdown-item></el-dropdown-menu></template>
      </el-dropdown>
    </div>
    <el-dialog v-model="searchOpen" title="快速前往" width="520px" class="page-search-dialog" @opened="searchInput?.focus()">
      <el-input ref="searchInput" v-model="query" placeholder="搜索练习、诊断或管理页面" clearable :prefix-icon="Search" size="large" />
      <div class="search-results"><router-link v-for="item in searchResults" :key="item.path" :to="item.path" @click="searchOpen = false"><el-icon><component :is="item.icon" /></el-icon><span>{{ item.title }}</span><small>{{ item.group }}</small><el-icon><Right /></el-icon></router-link><el-empty v-if="!searchResults.length" description="没有找到相关页面，试试其他关键词" :image-size="70" /></div>
    </el-dialog>
  </div>
</template>
<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowDown, Expand, HomeFilled, Right, Search } from '@element-plus/icons-vue'
import { useUserStore } from '@/store/user'
import { navigationGroups, pageLabel, roleLabels } from '@/ui/navigation'
defineEmits(['toggle-menu'])
const router = useRouter(), route = useRoute(), userStore = useUserStore()
const searchOpen = ref(false), query = ref(''), searchInput = ref()
const roleLabel = computed(() => roleLabels[userStore.role] || '用户')
const displayName = computed(() => userStore.user?.real_name || userStore.user?.username || '用户')
const currentTitle = computed(() => pageLabel(route.path, userStore.role))
const searchResults = computed(() => navigationGroups(userStore.role).flatMap(group => group.items.map(item => ({ ...item, group: group.title }))).filter(item => (item.title + item.group).includes(query.value.trim())))
function handleCommand(command) {
  if (command !== 'logout') return
  userStore.logout()
  router.push('/login')
}
</script>
