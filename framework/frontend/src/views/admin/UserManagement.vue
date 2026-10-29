<template>
  <section v-loading="loading" class="user-management">
    <div class="user-toolbar"><h1>用户管理</h1><el-button type="primary" @click="openCreate">新建账号</el-button></div>
    <p v-if="notice" role="status">{{ notice }}</p>
    <el-table :data="pageView.items" border>
      <el-table-column prop="username" label="用户名" min-width="120" />
      <el-table-column v-for="field in fields" :key="field.key" :label="field.label" min-width="100"><template #default="{ row }">{{ row[field.key] || 'null' }}</template></el-table-column>
      <el-table-column label="角色" width="90"><template #default="{ row }">{{ roleLabels[row.role] }}</template></el-table-column>
      <el-table-column label="状态" width="80"><template #default="{ row }">{{ row.is_active ? '启用' : '停用' }}</template></el-table-column>
      <el-table-column label="联系方式修改" width="120"><template #default="{ row }">{{ row.role !== 'admin' && row.contact_locked ? '已锁定' : '正常' }}</template></el-table-column>
      <el-table-column label="操作" min-width="260"><template #default="{ row }">
        <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
        <el-button v-if="row.role !== 'admin'" link type="primary" @click="openReset(row)">重置密码</el-button>
        <el-button link :disabled="row.id === user.user?.id || saving" @click="toggleActive(row)">{{ row.is_active ? '停用' : '启用' }}</el-button>
        <el-button v-if="row.role !== 'admin' && row.contact_locked" link type="primary" :disabled="saving" @click="unlockContact(row)">解锁联系方式</el-button>
      </template></el-table-column>
    </el-table>
    <ListPager :page="pageView.page" :total="pageView.total" @change="page = $event" />
    <el-dialog v-model="editorOpen" :title="editingId ? '编辑账号' : '新建账号'" width="min(520px, 94vw)" :close-on-click-modal="false" :before-close="closeEditor" @closed="clearEditor">
      <p v-if="formError" role="alert">{{ formError }}</p>
      <el-form label-position="top" @submit.prevent="saveUser">
        <el-form-item label="用户名"><el-input v-model.trim="form.username" :disabled="Boolean(editingId)" maxlength="50" autocomplete="off" /></el-form-item>
        <el-form-item v-if="!editingId" label="初始密码"><el-input v-model="form.password" type="password" show-password maxlength="1024" autocomplete="new-password" /></el-form-item>
        <el-form-item label="角色"><el-select v-model="form.role" :disabled="editingId === user.user?.id"><el-option label="学生" value="student" /><el-option label="教师" value="teacher" /><el-option v-if="originalRole === 'admin'" label="管理员" value="admin" /></el-select></el-form-item>
        <el-form-item :label="form.role === 'student' ? '姓名（学生必填）' : '姓名'"><el-input v-model.trim="form.real_name" maxlength="50" /></el-form-item>
        <el-form-item :label="form.role === 'student' ? '学号（学生必填）' : '学号'"><el-input v-model.trim="form.student_id" maxlength="30" placeholder="null" /></el-form-item>
        <el-form-item :label="form.role === 'student' ? '班级（学生必填）' : '班级'"><el-input v-model.trim="form.class_name" maxlength="50" placeholder="null" /></el-form-item>
        <div class="form-actions"><el-button :disabled="saving" @click="closeEditor()">取消</el-button><el-button type="primary" native-type="submit" :loading="saving">保存</el-button></div>
      </el-form>
    </el-dialog>
    <el-dialog v-model="resetOpen" title="重置密码" width="min(480px, 94vw)" :close-on-click-modal="false" :before-close="closeReset" @closed="resetPassword = ''">
      <p>{{ resetTarget?.username }}</p><p v-if="formError" role="alert">{{ formError }}</p>
      <el-form label-position="top" @submit.prevent="saveReset">
        <el-form-item label="新密码"><el-input v-model="resetPassword" type="password" show-password maxlength="1024" autocomplete="new-password" /></el-form-item>
        <p>保存后该账号的现有登录将失效。</p>
        <div class="form-actions"><el-button :disabled="saving" @click="closeReset()">取消</el-button><el-button native-type="submit" type="primary" :loading="saving">重置密码</el-button></div>
      </el-form>
    </el-dialog>
  </section>
</template>
<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessageBox } from 'element-plus'
import ListPager from '@/components/ListPager.vue'
import { paginate } from '@/domain/pagination'
import { accountError } from '@/domain/accountForms'
import { listAdminUsers, createAdminUser, updateAdminUser, resetAdminPassword, unlockAdminContact } from '@/api/admin'
import { useUserStore } from '@/store/user'
import { roleLabels } from '@/ui/navigation'

const user = useUserStore()
const users = ref([]), loading = ref(false), notice = ref(''), saving = ref(false)
const page = ref(1), pageView = computed(() => paginate(users.value, page.value))
const fields = [{ key: 'real_name', label: '姓名' }, { key: 'student_id', label: '学号' }, { key: 'class_name', label: '班级' }]
const editorOpen = ref(false), editingId = ref(null), originalRole = ref(''), formError = ref('')
const form = reactive({ username: '', password: '', role: 'student', real_name: '', student_id: '', class_name: '' })
const resetOpen = ref(false), resetTarget = ref(null), resetPassword = ref('')
function clearEditor() { form.password = '' }
function closeEditor(done) { if (saving.value) return; clearEditor(); editorOpen.value = false; if (done) done() }
function closeReset(done) { if (saving.value) return; resetPassword.value = ''; resetOpen.value = false; if (done) done() }
function openCreate() {
  editingId.value = null
  originalRole.value = ''
  formError.value = ''
  Object.assign(form, { username: '', password: '', role: 'student', real_name: '', student_id: '', class_name: '' })
  editorOpen.value = true
}
function openEdit(row) {
  editingId.value = row.id
  originalRole.value = row.role
  formError.value = ''
  Object.assign(form, { username: row.username, password: '', role: row.role, real_name: row.real_name || '', student_id: row.student_id || '', class_name: row.class_name || '' })
  editorOpen.value = true
}
function openReset(row) { resetTarget.value = row; resetPassword.value = ''; formError.value = ''; resetOpen.value = true }
async function loadUsers() {
  loading.value = true
  try { users.value = await listAdminUsers() }
  catch (error) { notice.value = accountError(error) }
  finally { loading.value = false }
}
function replaceUser(profile) {
  const index = users.value.findIndex(row => row.id === profile.id)
  if (index < 0) { users.value.push(profile); page.value = Math.ceil(users.value.length / 6) }
  else users.value.splice(index, 1, profile)
  if (profile.id === user.user?.id) user.setAuth(user.token, profile)
}
async function saveUser() {
  if (saving.value) return
  if (!editingId.value && (!form.username || !form.password)) { formError.value = '请输入用户名和初始密码'; return }
  if (!editingId.value && form.role === 'student' && (!form.real_name || !form.student_id || !form.class_name)) { formError.value = '新学生必须填写姓名、学号和班级'; return }
  saving.value = true
  formError.value = ''
  const data = { role: form.role, real_name: form.real_name || null, student_id: form.student_id || null, class_name: form.class_name || null }
  try {
    const profile = editingId.value ? await updateAdminUser(editingId.value, data) : await createAdminUser({ ...data, username: form.username, password: form.password })
    replaceUser(profile)
    editorOpen.value = false
    notice.value = '账号已保存'
  } catch (error) { formError.value = accountError(error) }
  finally { form.password = ''; saving.value = false }
}
async function saveReset() {
  if (saving.value || !resetTarget.value) return
  if (!resetPassword.value) { formError.value = '请输入新密码'; return }
  saving.value = true
  formError.value = ''
  try {
    replaceUser(await resetAdminPassword(resetTarget.value.id, { new_password: resetPassword.value }))
    resetOpen.value = false
    notice.value = '密码已重置，旧登录已失效'
  } catch (error) { formError.value = accountError(error) }
  finally { resetPassword.value = ''; saving.value = false }
}
async function toggleActive(row) {
  if (saving.value || row.id === user.user?.id) return
  try {
    await ElMessageBox.confirm(row.is_active ? `停用账号 ${row.username}？该账号将不能登录或继续操作，历史记录保留。` : `启用账号 ${row.username}？`, row.is_active ? '停用账号' : '启用账号', { confirmButtonText: '确认', cancelButtonText: '取消' })
  } catch { return }
  if (saving.value) return
  saving.value = true
  try { replaceUser(await updateAdminUser(row.id, { is_active: !row.is_active })); notice.value = row.is_active ? '账号已停用' : '账号已启用' }
  catch (error) { notice.value = accountError(error) }
  finally { saving.value = false }
}
async function unlockContact(row) {
  if (saving.value || row.role === 'admin' || !row.contact_locked) return
  saving.value = true
  try {
    replaceUser(await unlockAdminContact(row.id))
    notice.value = '联系方式修改已解锁'
  } catch (error) { notice.value = accountError(error) }
  finally { saving.value = false }
}
onMounted(loadUsers)
</script>
<style scoped>
.user-toolbar{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:24px}.user-toolbar h1{margin:0}.form-actions{display:flex;justify-content:flex-end;gap:8px}.user-management [role=alert]{color:#a52727;overflow-wrap:anywhere}.user-management [role=status]{overflow-wrap:anywhere}
</style>
