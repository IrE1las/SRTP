<template>
  <div class="sidebar">
    <div class="sidebar-caption"><span class="caption-mark"></span> 知行 · 实训平台 <span class="version-tag">SRTP</span></div>
    <nav aria-label="主导航" class="sidebar-navigation">
      <section v-for="item in items" :key="item.path" class="s1-nav-group">
        <div class="nav-parent">
          <router-link v-if="!item.children?.length || item.overview" :to="item.path" :class="['nav-item', { active: isActive(item) }]" :aria-current="route.path === item.path ? 'page' : undefined" @click="$emit('navigate')">{{ item.title }}</router-link>
          <button v-else type="button" class="nav-item" :class="{active:isActive(item)}" :aria-expanded="!!expanded[item.path]" @click="toggle(item.path)">{{ item.title }}</button>
          <button v-if="item.children" type="button" class="nav-toggle" :aria-label="`${expanded[item.path] ? '收起' : '展开'}${item.title}`" :aria-expanded="!!expanded[item.path]" @click="toggle(item.path)">{{ expanded[item.path] ? '⌃' : '⌄' }}</button>
        </div>
        <div v-if="item.children && expanded[item.path]" class="nav-children">
          <router-link v-for="child in item.children" :key="child.path" :to="child.path" :class="['nav-item', { active: isActive(child) }]" :aria-current="route.path === child.path ? 'page' : undefined" @click="$emit('navigate')">{{ child.title }}</router-link>
          <p v-if="!item.children.length" class="nav-empty">{{ item.empty }}</p>
        </div>
      </section>
    </nav>
  </div>
</template>
<script setup>
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useUserStore } from '@/store/user'
import { navigationForRole } from '@/ui/navigation'
defineEmits(['navigate'])
const route = useRoute(), user = useUserStore(), expanded = ref({})
const items = computed(() => navigationForRole(user.role))
function toggle(path) { expanded.value[path] = !expanded.value[path] }
function isActive(item) { return item.children?.length ? (item.overview && route.path === item.path) || item.children.some(child => isActive(child)) : route.path === item.path || (item.path !== '/admin' && route.path.startsWith(item.path + '/')) }
</script>
<style scoped>
.s1-nav-group{margin:8px 0}.nav-parent{display:flex;align-items:center}.nav-parent>.nav-item{flex:1;text-align:left;background:transparent;border:0;cursor:pointer;font:inherit}.nav-parent>.nav-item.active{background:#e6f2fa;color:#0075b7}.nav-toggle{border:0;background:transparent;color:#47657c;font-size:20px;cursor:pointer;padding:12px}.nav-children{margin-left:16px;border-left:2px solid #e0eaf3;padding-left:8px}.nav-empty{font-size:13px;line-height:1.8;color:#586f82;padding:5px 12px}.nav-item:focus-visible,.nav-toggle:focus-visible{outline:2px solid #0075b7}
</style>
