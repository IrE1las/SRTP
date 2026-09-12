<template>
  <div class="login-page">
    <section class="login-story" aria-label="西南交通大学主题">
      <img class="login-campus" src="/brand/swjtu-campus.png" alt="西南交通大学校门" />
      <a class="login-university" href="https://www.swjtu.edu.cn/" target="_blank" rel="noopener noreferrer"><img src="/brand/swjtu-logo.png" alt="西南交通大学 Southwest Jiaotong University" /></a>
      <div class="login-story-content">
        <p class="login-eyebrow"><span></span> RAILWAY INTERLOCKING LAB</p>
        <h1>精勤求学<br /><span>知行致远</span></h1>
        <div class="story-rule"></div>
        <p class="login-story-description">在每一次实践中理解联锁逻辑<br />让知识连接思考，让思考指引行动</p>
        <div class="story-topics"><span>自主作答</span><i></i><span>精准定位</span><i></i><span>错误解释</span></div>
      </div>
      <div class="story-footer"><span>竢实扬华 · 自强不息</span><a href="https://www.swjtu.edu.cn/xxgk/xswh.htm" target="_blank" rel="noopener noreferrer">走进交大文化 ↗</a></div>
    </section>
    <section class="login-panel">
      <div class="login-panel-top"><span>SRTP <i>/</i> 实训平台</span><a href="https://www.swjtu.edu.cn/" target="_blank" rel="noopener noreferrer">学校官网 ↗</a></div>
      <div class="login-form-wrap">
        <p class="form-eyebrow">WELCOME TO LEARN</p>
        <h2>{{ activeTab === 'login' ? '欢迎回到实训课堂' : '开启你的实训之旅' }}</h2>
        <p class="form-intro">铁路计算机联锁仿真实训系统</p>
        <el-tabs v-model="activeTab" class="login-tabs">
          <el-tab-pane label="账号登录" name="login">
            <el-form ref="loginFormRef" :model="loginForm" :rules="loginRules" label-position="top" size="large" @submit.prevent="handleLogin">
              <el-form-item label="用户名" prop="username"><el-input v-model.trim="loginForm.username" placeholder="请输入用户名" autocomplete="username" :prefix-icon="User" /></el-form-item>
              <el-form-item label="密码" prop="password"><el-input v-model="loginForm.password" type="password" placeholder="请输入密码" show-password autocomplete="current-password" :prefix-icon="Lock" /></el-form-item>
              <p class="login-hint"><el-icon><Lock /></el-icon> 使用你的实训平台账号登录</p>
              <el-button native-type="submit" type="primary" class="submit-button" :loading="loginLoading">登录 <el-icon><Right /></el-icon></el-button>
            </el-form>
            <div class="login-bottom-note"><span></span><p>理解错误，是掌握知识的开始</p><span></span></div>
          </el-tab-pane>
          <el-tab-pane label="注册账号" name="register">
            <el-form ref="registerFormRef" :model="registerForm" :rules="registerRules" label-position="top" size="large" @submit.prevent="handleRegister">
              <el-form-item label="用户名" prop="username"><el-input v-model.trim="registerForm.username" placeholder="3-50 位用户名" autocomplete="username" /></el-form-item>
              <el-form-item label="密码" prop="password"><el-input v-model="registerForm.password" type="password" show-password placeholder="至少 6 位" autocomplete="new-password" /></el-form-item>
              <div class="register-row">
                <el-form-item label="真实姓名" prop="real_name"><el-input v-model.trim="registerForm.real_name" placeholder="请输入真实姓名" autocomplete="name" /></el-form-item>
                <el-form-item label="角色" prop="role"><el-select v-model="registerForm.role" class="full-width"><el-option label="学生" value="student" /><el-option label="教师" value="teacher" /></el-select></el-form-item>
              </div>
              <div v-if="registerForm.role === 'student'" class="register-row">
                <el-form-item label="学号" prop="student_id"><el-input v-model.trim="registerForm.student_id" placeholder="请输入学号" /></el-form-item>
                <el-form-item label="班级" prop="class_name"><el-input v-model.trim="registerForm.class_name" placeholder="请输入班级" /></el-form-item>
              </div>
              <el-button native-type="submit" type="primary" class="submit-button" :loading="registerLoading">创建账号 <el-icon><Right /></el-icon></el-button>
            </el-form>
          </el-tab-pane>
        </el-tabs>
      </div>
      <footer class="login-panel-footer">SRTP · 铁路联锁实训 <span>视觉参考：西南交通大学</span></footer>
    </section>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { User, Lock, Right } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'

import { register } from '@/api/auth'
import { roleHomeMap } from '@/router'
import { useUserStore } from '@/store/user'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const activeTab = ref('login')
const loginFormRef = ref()
const registerFormRef = ref()
const loginLoading = ref(false)
const registerLoading = ref(false)

const loginForm = reactive({
  username: '',
  password: '',
})

const registerForm = reactive({
  username: '',
  password: '',
  real_name: '',
  role: 'student',
  student_id: '',
  class_name: '',
})

const loginRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

const registerRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 50, message: '用户名长度应为 3-50 位', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 128, message: '密码长度应为 6-128 位', trigger: 'blur' },
  ],
  role: [{ required: true, message: '请选择角色', trigger: 'change' }],
}

async function handleLogin() {
  if (loginLoading.value) return
  if (!await loginFormRef.value.validate().catch(() => false)) return
  loginLoading.value = true
  try {
    const user = await userStore.login(loginForm)
    ElMessage.success('登录成功')
    const redirect = route.query.redirect
    router.push(typeof redirect === 'string' ? redirect : roleHomeMap[user.role])
  } catch (error) {
    if (error.response?.status === 401) ElMessage.error('用户名或密码不正确，请重新输入')
    // Other API errors are displayed by the shared request interceptor.
  } finally {
    loginLoading.value = false
  }
}

async function handleRegister() {
  if (registerLoading.value) return
  if (!await registerFormRef.value.validate().catch(() => false)) return
  registerLoading.value = true
  try {
    await register({ ...registerForm })
    ElMessage.success('注册成功，请登录')
    activeTab.value = 'login'
    loginForm.username = registerForm.username
    loginForm.password = ''
  } catch {
    // The shared request interceptor displays the registration error.
  } finally {
    registerLoading.value = false
  }
}
</script>

<style scoped>
.login-page { min-height: 100vh; display: grid; grid-template-columns: 53% 47%; background: #fff; }
.login-story { position: relative; background: #082e60; min-height: 100vh; overflow: hidden; color: #fff; isolation: isolate; display: flex; flex-direction: column; padding: 44px 52px 30px; }
.login-campus { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; object-position: 38% center; z-index: -3; }
.login-story::before { content: ""; position: absolute; inset: 0; z-index: -2; background: linear-gradient(180deg, #062555a8, #092e66a6 40%, #072557eb 100%); }
.login-story::after { content: ""; position: absolute; inset: 0; z-index: -1; background: linear-gradient(90deg, #07234e65, transparent 80%); }
.login-university { display: inline-block; width: 274px; }.login-university img { width: 100%; display: block; }
.login-story-content { margin: auto 0; padding: 60px 0 90px; }
.login-eyebrow { display: flex; align-items: center; gap: 14px; color: #d0dfed; font-size: var(--ui-text-sm); letter-spacing: 2.5px; margin: 0 0 32px; }
.login-eyebrow span { width: 27px; height: 1px; background: #d4b778; }
.login-story h1 { font-family: "STKaiti", "KaiTi", "SimSun", serif; font-size: clamp(45px, 5.1vw, 76px); font-weight: 400; letter-spacing: 12px; line-height: 1.5; margin: 0; }
.login-story h1 span { color: #f4e8cc; }
.story-rule { width: 46px; height: 2px; background: #c7ae7f; margin: 28px 0; }
.login-story-description { color: #dce5f0; font-size: var(--ui-text-body); line-height: 2.2; letter-spacing: 2px; }
.story-topics { display: flex; gap: 19px; align-items: center; margin-top: 34px; color: #c6d8e9; font-size: var(--ui-text-meta); letter-spacing: 1px; }.story-topics i { width: 3px; height: 3px; background: #cfb881; border-radius: 50%; }
.story-footer { display: flex; justify-content: space-between; gap: 15px; border-top: 1px solid #ffffff30; padding-top: 20px; font-size: var(--ui-text-meta); color: #c2d2e6; letter-spacing: 1px; }.story-footer a { color: #dbe5f0; font-size: var(--ui-text-sm); }
.login-panel { display: flex; flex-direction: column; min-width: 0; padding: 40px 50px 27px; }
.login-panel-top { display: flex; align-items: center; justify-content: space-between; color: #586f82; font-size: var(--ui-text-meta); letter-spacing: 1px; }.login-panel-top i { font-style: normal; color: #c7d0d9; margin: 0 8px; }.login-panel-top a { font-size: var(--ui-text-sm); color: #586f82; }
.login-form-wrap { width: 100%; max-width: 374px; margin: auto; padding: 58px 0 75px; }
.form-eyebrow { font-size: var(--ui-text-xs); color: var(--swjtu-blue); letter-spacing: 2.4px; font-weight: 600; margin: 0 0 17px; }
.login-form-wrap h2 { margin: 0; font-size: 30px; font-weight: 600; letter-spacing: 1px; color: #183850; }
.form-intro { color: #586f82; font-size: var(--ui-text-base); margin: 14px 0 32px; }
.login-tabs :deep(.el-tabs__header) { margin-bottom: 30px; }.login-tabs :deep(.el-tabs__item) { font-size: var(--ui-text-base); color: #586f82; height: 43px; }.login-tabs :deep(.el-tabs__item.is-active) { color: var(--swjtu-blue); font-weight: 600; }.login-tabs :deep(.el-tabs__nav-wrap::after) { height: 1px; background: #e6ecf2; }
.login-tabs :deep(.el-form-item) { margin-bottom: 24px; }.login-tabs :deep(.el-form-item__label) { font-size: var(--ui-text-base); margin-bottom: 9px; line-height: 1.5; color: #4a6277; }
.login-tabs :deep(.el-input__wrapper), .login-tabs :deep(.el-select__wrapper) { min-height: 46px; background: #fcfdfe; border-radius: 6px; box-shadow: 0 0 0 1px #e0e7ee inset; }.login-tabs :deep(.el-input__wrapper.is-focus), .login-tabs :deep(.el-select__wrapper.is-focused) { box-shadow: 0 0 0 1px var(--swjtu-blue) inset; }
.login-tabs :deep(.el-input__inner) { font-size: var(--ui-text-base); }.login-tabs :deep(.el-input__prefix) { margin-right: 6px; color: #586f82; }
.login-hint { display: flex; align-items: center; gap: 7px; color: #586f82; font-size: var(--ui-text-sm); margin: -4px 0 23px; }
.submit-button { width: 100%; height: 46px; border-radius: 6px; font-size: var(--ui-text-body); letter-spacing: 2px; box-shadow: 0 5px 15px #0075b71c; }.submit-button :deep(.el-icon) { margin-left: 20px; }
.login-bottom-note { display: flex; align-items: center; gap: 13px; margin-top: 27px; color: #586f82; font-size: var(--ui-text-sm); }.login-bottom-note > span { height: 1px; flex: 1; background: #edf0f5; }
.login-panel-footer { display: flex; justify-content: space-between; gap: 15px; color: #586f82; font-size: var(--ui-text-xs); }
.register-row { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 16px; }.full-width { width: 100%; }
@media (max-width: 1100px) { .login-story { padding: 35px; }.login-panel { padding: 36px 38px 25px; }.login-story h1 { letter-spacing: 9px; }.login-panel-footer { flex-direction: column; gap: 7px; }.story-footer { flex-direction: column; gap: 12px; } }
@media (max-width: 760px) { .login-page { grid-template-columns: 1fr; }.login-story { min-height: 240px; padding: 25px 28px; }.login-university { width: 195px; }.login-story-content { margin: 0; padding: 35px 0 6px; }.login-story h1 { font-size: 34px; letter-spacing: 7px; }.login-story h1 br { display: none; }.login-story h1 span { margin-left: 15px; }.login-eyebrow { margin-bottom: 10px; font-size: var(--ui-text-xs); letter-spacing: 1.4px; }.login-story-description, .story-rule, .story-topics, .story-footer { display: none; }.login-campus { object-position: center 65%; }.login-story::before { background: linear-gradient(90deg, #092c61ee, #092e6690); }.login-panel { padding: 23px 28px; min-height: calc(100vh - 240px); }.login-form-wrap { padding: 40px 0 35px; }.login-form-wrap h2 { font-size: 28px; }.login-panel-footer { flex-direction: row; flex-wrap: wrap; line-height: 1.8; } }
@media (max-width: 390px) { .login-story h1 { font-size: 31px; letter-spacing: 4px; }.login-story h1 span { margin-left: 12px; }.login-panel { padding: 23px; } }
</style>
