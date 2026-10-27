<template>
  <section class="profile-home" v-loading="loading">
    <h1>首页</h1><p class="profile-role">{{ roleLabels[user.role] }} · 个人资料</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <dl>
      <template v-for="field in fields" :key="field.label"><dt>{{ field.label }}</dt><dd>{{ field.value || 'null' }}</dd></template>
    </dl>
    <div class="password-row"><span>修改密码</span><el-button disabled>待S2实现</el-button></div>
    <p class="profile-note">邮箱、手机号保存及修改密码将在S2实现。</p>
  </section>
</template>
<script setup>
import { computed, onMounted, ref } from 'vue'
import { useUserStore } from '@/store/user'
import { roleLabels } from '@/ui/navigation'
const user = useUserStore(), loading = ref(false), error = ref('')
const fields = computed(() => [
  { label: user.isStudent ? '学生姓名' : '姓名', value: user.user?.real_name },
  { label: '学生学号', value: user.isStudent ? user.user?.student_id : null },
  { label: '学生班级', value: user.isStudent ? user.user?.class_name : null },
  { label: '电子邮箱', value: null }, { label: '手机号', value: null },
])
onMounted(async () => { loading.value = true; try { await user.fetchProfile() } catch { error.value = '个人资料加载失败，请重试。' } finally { loading.value = false } })
</script>
<style scoped>
.profile-home{max-width:820px;background:white;border:1px solid #dce7f0;padding:32px;border-radius:10px}.profile-home h1{margin:0 0 12px;color:#183850}.profile-role,.profile-note{color:#586f82;line-height:1.8}.profile-home dl{margin:30px 0}.profile-home dt{color:#586f82;margin-top:22px}.profile-home dd{margin:8px 0 0;padding:10px 0 14px;border-bottom:1px solid #e8eff5;color:#19334d;overflow-wrap:anywhere}.password-row{display:flex;align-items:center;justify-content:space-between;gap:18px}
</style>
