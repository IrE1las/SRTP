<template>
  <p v-if="user.role === 'admin'" class="operation-management-link"><router-link to="/operations/manage">操作题管理</router-link></p>
  <section class="profile-home" v-loading="loading">
    <h1>首页</h1>
    <p v-if="notice" role="status">{{ notice }}</p>
    <dl>
      <template v-for="field in fields" :key="field.label">
        <dt>{{ field.label }}</dt><dd>{{ field.value || 'null' }}</dd>
      </template>
    </dl>
    <el-form label-position="top" @submit.prevent="saveContact">
      <el-form-item label="电子邮箱"><el-input v-model="contact.email" maxlength="254" autocomplete="off" :disabled="!ready || savingContact || contactLocked" /></el-form-item>
      <el-form-item label="手机号"><el-input v-model="contact.phone" maxlength="32" autocomplete="off" :disabled="!ready || savingContact || contactLocked" /></el-form-item>
      <p v-if="contactLocked" role="alert">联系方式修改已锁定，请联系管理员解锁</p>
      <el-button native-type="submit" type="primary" :disabled="!ready || savingPassword || savingContact || contactLocked">保存联系方式</el-button>
    </el-form>
    <el-dialog v-model="contactDialogOpen" title="确认保存联系方式" width="min(440px, 94vw)" :close-on-click-modal="false" :before-close="closeContactDialog" @closed="clearContactDialog">
      <el-form label-position="top" @submit.prevent="confirmContact">
        <p v-if="contactError" role="alert">{{ contactError }}</p>
        <el-form-item label="当前密码"><el-input v-model="contactPassword" type="password" show-password autocomplete="current-password" maxlength="1024" :disabled="savingContact || contactLocked" /></el-form-item>
        <div class="contact-actions"><el-button :disabled="savingContact" @click="closeContactDialog()">取消</el-button><el-button native-type="submit" type="primary" :loading="savingContact" :disabled="contactLocked">确认</el-button></div>
      </el-form>
    </el-dialog>
    <div class="password-row"><h2>修改密码</h2><el-button :disabled="!ready || savingPassword" @click="togglePassword">{{ passwordOpen ? '收起' : '修改密码' }}</el-button></div>
    <el-form v-if="passwordOpen" label-position="top" @submit.prevent="savePassword">
      <el-form-item label="当前密码"><el-input v-model="password.current_password" type="password" show-password autocomplete="current-password" maxlength="1024" /></el-form-item>
      <el-form-item label="新密码"><el-input v-model="password.new_password" type="password" show-password autocomplete="new-password" maxlength="1024" /></el-form-item>
      <el-form-item label="重复新密码"><el-input v-model="password.confirm_password" type="password" show-password autocomplete="new-password" maxlength="1024" /></el-form-item>
      <el-button native-type="submit" type="primary" :loading="savingPassword" :disabled="savingContact">修改并重新登录</el-button>
    </el-form>
  </section>
</template>
<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/store/user'
import { updateContact, changePassword } from '@/api/auth'
import { accountError } from '@/domain/accountForms'

const user = useUserStore(), router = useRouter()
const loading = ref(false), ready = ref(false), notice = ref('')
const savingContact = ref(false), savingPassword = ref(false), passwordOpen = ref(false)
const contact = reactive({ email: '', phone: '' })
const contactDialogOpen = ref(false), contactPassword = ref(''), contactError = ref(''), pendingContact = ref(null)
const contactLocked = computed(() => user.user?.role !== 'admin' && Boolean(user.user?.contact_locked))
const password = reactive({ current_password: '', new_password: '', confirm_password: '' })
const fields = computed(() => [
  { label: user.isStudent ? '学生姓名' : '姓名', value: user.user?.real_name },
  { label: '学生学号', value: user.isStudent ? user.user?.student_id : null },
  { label: '学生班级', value: user.isStudent ? user.user?.class_name : null },
])
function clearPassword() {
  Object.assign(password, { current_password: '', new_password: '', confirm_password: '' })
}
function togglePassword() {
  passwordOpen.value = !passwordOpen.value
  clearPassword()
}
function clearContactDialog() {
  contactPassword.value = ''
  contactError.value = ''
  pendingContact.value = null
}
function closeContactDialog(done) {
  if (savingContact.value) return
  contactDialogOpen.value = false
  clearContactDialog()
  if (done) done()
}
function saveContact() {
  if (!ready.value || savingContact.value || savingPassword.value || contactLocked.value || contactDialogOpen.value) return
  clearContactDialog()
  pendingContact.value = { email: contact.email.trim() || null, phone: contact.phone.trim() || null }
  contactDialogOpen.value = true
}
async function confirmContact() {
  if (!ready.value || savingContact.value || contactLocked.value || !contactDialogOpen.value || !pendingContact.value) return
  if (!contactPassword.value) { contactError.value = '请输入当前密码'; return }
  savingContact.value = true
  contactError.value = ''
  try {
    const profile = await updateContact({ ...pendingContact.value, current_password: contactPassword.value })
    user.setAuth(user.token, profile)
    contact.email = profile.email || ''
    contact.phone = profile.phone || ''
    contactDialogOpen.value = false
    ElMessage.success('联系方式已保存')
  } catch (error) {
    contactError.value = accountError(error)
    if ([400, 403].includes(error?.response?.status)) {
      try { await user.fetchProfile() } catch { /* The original save error remains visible. */ }
    }
  } finally { contactPassword.value = ''; savingContact.value = false }
}
async function savePassword() {
  if (!ready.value || savingPassword.value || savingContact.value) return
  if (!password.current_password || !password.new_password) { notice.value = '请输入当前密码和新密码'; return }
  if (password.new_password !== password.confirm_password) { notice.value = '两次新密码不一致'; return }
  savingPassword.value = true
  notice.value = ''
  try {
    await changePassword({ ...password })
    user.logout()
    await router.replace({ path: '/login', query: { passwordChanged: '1' } })
  } catch (error) { notice.value = accountError(error) }
  finally { clearPassword(); savingPassword.value = false }
}
onMounted(async () => {
  loading.value = true
  try {
    const profile = await user.fetchProfile()
    contact.email = profile.email || ''
    contact.phone = profile.phone || ''
    ready.value = true
  } catch (error) { notice.value = accountError(error) }
  finally { loading.value = false }
})
</script>
<style scoped>
.profile-home{max-width:820px;background:white;border:1px solid #dce7f0;padding:32px;border-radius:10px}.profile-home h1{margin:0 0 24px;color:#183850}.profile-home dl{margin:0 0 24px}.profile-home dt{color:#586f82;margin-top:22px}.profile-home dd{margin:8px 0 0;padding:10px 0 14px;border-bottom:1px solid #e8eff5;color:#19334d;overflow-wrap:anywhere}.password-row{display:flex;align-items:center;justify-content:space-between;gap:18px;margin:28px 0 20px}.password-row h2{font-size:18px;margin:0}.profile-home [role=status]{color:#304e66;overflow-wrap:anywhere}@media(max-width:600px){.profile-home{padding:20px}}
.contact-actions{display:flex;justify-content:flex-end;gap:8px}.profile-home [role=alert]{color:#a52727;overflow-wrap:anywhere}
</style>
