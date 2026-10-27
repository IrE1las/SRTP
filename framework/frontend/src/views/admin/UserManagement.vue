<template><section v-loading="loading"><h1>用户管理</h1><p>现有账号列表。建号、身份编辑、停用和密码重置待S2实现。</p><p v-if="error" role="alert">{{ error }}</p><el-table :data="pageView.items" border><el-table-column prop="username" label="用户名"/><el-table-column v-for="field in fields" :key="field.key" :label="field.label"><template #default="{row}">{{ row[field.key] || 'null' }}</template></el-table-column></el-table><ListPager :page="pageView.page" :total="pageView.total" @change="page=$event"/></section></template>
<script setup>
import { computed, onMounted, ref } from 'vue'
import ListPager from '@/components/ListPager.vue'
import { paginate } from '@/domain/pagination'
import { listAdminUsers } from '@/api/admin'
const users = ref([]), loading = ref(false), error = ref('')
const page=ref(1),pageView=computed(()=>paginate(users.value,page.value))
const fields = [{key:'real_name',label:'姓名'},{key:'role',label:'角色'},{key:'student_id',label:'学号'},{key:'class_name',label:'班级'}]
onMounted(async () => { loading.value = true; try { users.value = await listAdminUsers() } catch { error.value = '用户列表加载失败。' } finally { loading.value = false } })
</script>
