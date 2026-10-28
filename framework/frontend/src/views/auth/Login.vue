<template>
  <div class="login-page">
    <section class="login-story" aria-label="西南交通大学">
      <img class="login-campus" src="/brand/swjtu-campus.png" alt="西南交通大学校门" />
      <a class="login-university" href="https://www.swjtu.edu.cn/" target="_blank" rel="noopener noreferrer"><img src="/brand/swjtu-logo.png" alt="西南交通大学" /></a>
    </section>
    <section class="login-panel">
      <div class="login-form-wrap">
        <h1>铁路计算机联锁仿真实训系统</h1>
        <p v-if="route.query.passwordChanged === '1'" role="status">密码已修改，请重新登录。</p>
        <el-form ref="loginFormRef" :model="loginForm" :rules="loginRules" label-position="top" size="large" @submit.prevent="handleLogin">
          <el-form-item label="用户名" prop="username"><el-input v-model.trim="loginForm.username" maxlength="50" autocomplete="username" :prefix-icon="User" /></el-form-item>
          <el-form-item label="密码" prop="password"><el-input v-model="loginForm.password" type="password" show-password autocomplete="current-password" maxlength="1024" :prefix-icon="Lock" /></el-form-item>
          <el-button native-type="submit" type="primary" class="submit-button" :loading="loginLoading">登录</el-button>
        </el-form>
        <p class="login-hint">账号由管理员建立。</p>
      </div>
    </section>
  </div>
</template>
<script setup>
import { reactive, ref } from 'vue'
import { User, Lock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { roleHomeMap } from '@/router'
import { useUserStore } from '@/store/user'
const router = useRouter(), route = useRoute(), userStore = useUserStore()
const loginFormRef = ref(), loginLoading = ref(false)
const loginForm = reactive({ username: '', password: '' })
const loginRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}
async function handleLogin() {
  if (loginLoading.value) return
  if (!await loginFormRef.value.validate().catch(() => false)) return
  loginLoading.value = true
  try {
    const profile = await userStore.login({ ...loginForm })
    const redirect = route.query.redirect
    router.push(typeof redirect === 'string' && redirect.startsWith('/') && !redirect.startsWith('//') ? redirect : roleHomeMap[profile.role])
  } catch (error) {
    if (error.response?.status === 401) ElMessage.error('用户名或密码错误，或账号已停用')
  } finally { loginForm.password = ''; loginLoading.value = false }
}
</script>
<style scoped>
.login-page{min-height:100vh;display:grid;grid-template-columns:53% 47%;background:#fff}.login-story{position:relative;background:#082e60;min-height:100vh;overflow:hidden;isolation:isolate;padding:44px 52px}.login-campus{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:38% center;z-index:-1;opacity:.55}.login-university img{width:min(100%,380px)}.login-panel{display:flex;align-items:center;justify-content:center;padding:48px 36px}.login-form-wrap{width:100%;max-width:420px}.login-form-wrap h1{font-size:24px;color:#183850;line-height:1.5;margin:0 0 36px}.submit-button{width:100%;margin-top:12px}.login-hint{font-size:14px;color:#586f82;margin-top:20px}@media(max-width:768px){.login-page{grid-template-columns:1fr}.login-story{min-height:140px;padding:24px}.login-university img{max-width:300px}.login-panel{padding:32px 24px}}
</style>
