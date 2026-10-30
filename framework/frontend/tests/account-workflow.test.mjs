import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { parse } from '@vue/compiler-sfc'
import { accountError } from '../src/domain/accountForms.js'
import { paginate } from '../src/domain/pagination.js'

const failure = message => ({ response: { status: 400, data: { detail: message } } })
async function harness(path, { mocks = {}, expose = [], role = 'student' } = {}) {
  const source = await readFile(new URL('../src/' + path, import.meta.url), 'utf8')
  const descriptor = parse(source).descriptor
  const calls = []
  const profile = { id: 7, role, real_name: null, student_id: null, class_name: null, email: null, phone: null }
  const user = reactive({ user: profile, token: 'test-token', isStudent: role === 'student',
    fetchProfile: async () => user.user,
    setAuth: (token, value) => { user.user = value; calls.push(['setAuth', token, value]) },
    logout: () => { user.user = null; user.token = ''; calls.push(['logout']) },
    login: async body => { calls.push(['login', body]); return profile },
  })
  let mounted
  const deps = { computed, nextTick, reactive, ref, watch, onMounted: fn => { mounted = fn },
    useUserStore: () => user, useRouter: () => ({ replace: async value => calls.push(['replace', value]), push: value => calls.push(['push', value]) }),
    useRoute: () => ({ query: {} }), roleHomeMap: { student: '/student/dashboard' },
    roleLabels: { student: '学生', teacher: '教师', admin: '管理员' }, accountError, paginate,
    updateContact: async body => { calls.push(['contact', body]); return { ...profile, email: body.email, phone: body.phone } },
    changePassword: async body => calls.push(['password', body]),
    listAdminUsers: async () => Array.from({ length: 13 }, (_, i) => ({ id: i + 1, username: 'user' + i, role: 'student', is_active: true })),
    createAdminUser: async body => { calls.push(['create', body]); return { ...profile, ...body, id: 14, password: undefined } },
    updateAdminUser: async (id, body) => { calls.push(['update', id, body]); return { id, ...body } },
    resetAdminPassword: async (id, body) => { calls.push(['reset', id, body]); return { id, role: 'student' } },
    unlockAdminContact: async id => { calls.push(['unlock', id]); return { id, role: 'student', contact_locked: false, contact_failures: 0 } },
    ElMessageBox: { confirm: async () => calls.push(['confirm']) }, ElMessage: { error: message => calls.push(['error', message]), success: message => calls.push(['success', message]) },
    User: {}, Lock: {}, ...mocks,
  }
  const script = descriptor.scriptSetup.content.replace(/^import .*$/gm, '')
  const state = new Function(...Object.keys(deps), script + '\nreturn {' + expose.join(',') + '};')(...Object.values(deps))
  if (mounted) await mounted()
  return { state, calls, user, template: descriptor.template.content, source }
}

test('contact Save opens a password dialog, confirmation alone persists the staged values, cancel does nothing', async () => {
  const { state, calls, template } = await harness('views/shared/ProfileHome.vue', {
    expose: ['contact', 'fields', 'saveContact', 'confirmContact', 'contactDialogOpen', 'contactPassword', 'contactError', 'closeContactDialog'],
  })
  assert.equal(state.fields.value.length, 3)
  assert.ok(template.includes('<dd>{{ field.value || \'null\' }}</dd>'))
  assert.ok(!/v-model[^\n]*(student_id|class_name|real_name)/.test(template))
  await state.saveContact()
  assert.equal(state.contactDialogOpen.value, true)
  assert.equal(calls.length, 0)
  await state.confirmContact()
  assert.equal(calls.length, 0)
  assert.equal(state.contactError.value, '请输入当前密码')
  state.contactPassword.value = 'test-secret'
  await state.confirmContact()
  assert.deepEqual(calls[0], ['contact', { email: null, phone: null, current_password: 'test-secret' }])
  assert.equal(state.contactPassword.value, '')
  assert.equal(state.contactDialogOpen.value, false)
  assert.ok(calls.some(row => row[0] === 'success' && row[1] === '联系方式已保存'))
  await state.saveContact()
  state.contactPassword.value = 'discard'
  state.closeContactDialog()
  assert.equal(state.contactDialogOpen.value, false)
  assert.equal(state.contactPassword.value, '')
  assert.equal(calls.filter(row => row[0] === 'contact').length, 1)
})

test('failed contact save keeps form available and does not log the user out', async () => {
  const { state, calls, user } = await harness('views/shared/ProfileHome.vue', {
    mocks: { updateContact: async () => { throw failure('当前密码错误，未保存任何变更') } },
    expose: ['contact', 'saveContact', 'confirmContact', 'contactPassword', 'contactError', 'savingContact', 'contactDialogOpen'],
  })
  state.contact.email = 'sample@example.com'
  await state.saveContact()
  state.contactPassword.value = 'wrong'
  await state.confirmContact()
  assert.equal(user.user.email, null)
  assert.match(state.contactError.value, /当前密码错误/)
  assert.equal(state.contactPassword.value, '')
  assert.equal(state.contactDialogOpen.value, true)
  assert.equal(state.savingContact.value, false)
  assert.ok(!calls.some(row => row[0] === 'logout'))
})

test('profile load failure disables mutation until a successful reload', async () => {
  const { state, calls } = await harness('views/shared/ProfileHome.vue', {
    mocks: { useUserStore: () => ({ user: null, fetchProfile: async () => { throw failure('加载失败') } }) },
    expose: ['contact', 'ready', 'saveContact'],
  })
  assert.equal(state.ready.value, false)
  await state.saveContact()
  assert.equal(calls.length, 0)
})

test('the fifth failure refreshes the persistent lock, blocks retries and cannot be bypassed by reopening the dialog', async () => {
  let errors = 0
  const store = reactive({ user: { id: 7, role: 'teacher', contact_locked: false },
    fetchProfile: async () => {
      store.user = { ...store.user, contact_locked: errors >= 5, contact_failures: errors }
      return store.user
    },
  })
  const { state } = await harness('views/shared/ProfileHome.vue', {
    expose: ['contactLocked', 'contactPassword', 'contactDialogOpen', 'saveContact', 'confirmContact', 'closeContactDialog'],
    mocks: { useUserStore: () => store, updateContact: async () => {
      errors++
      throw { response: { status: errors >= 5 ? 403 : 400, data: { detail: '当前密码错误' } } }
    } },
  })
  state.saveContact()
  for (let i = 0; i < 5; i++) { state.contactPassword.value = 'wrong'; await state.confirmContact() }
  assert.equal(state.contactLocked.value, true)
  state.contactPassword.value = 'correct'
  await state.confirmContact()
  assert.equal(errors, 5)
  state.closeContactDialog()
  state.saveContact()
  assert.equal(state.contactDialogOpen.value, false)
})

test('administrator explicitly unlocks contacts without enabling or resetting the target account', async () => {
  const { state, calls } = await harness('views/admin/UserManagement.vue', { role: 'admin', expose: ['unlockContact', 'users', 'notice'] })
  await state.unlockContact({ id: 2, role: 'student', contact_locked: true, is_active: false })
  assert.deepEqual(calls, [['unlock', 2]])
  assert.equal(state.users.value.find(row => row.id === 2).contact_locked, false)
  assert.equal(state.notice.value, '联系方式修改已解锁')
})

test('password confirmation blocks mismatches and only successful change logs out and returns to login', async () => {
  const { state, calls } = await harness('views/shared/ProfileHome.vue', { expose: ['password', 'savePassword', 'notice'] })
  Object.assign(state.password, { current_password: 'old', new_password: 'new', confirm_password: 'different' })
  await state.savePassword()
  assert.match(state.notice.value, /不一致/)
  assert.equal(calls.length, 0)
  state.password.confirm_password = 'new'
  await state.savePassword()
  assert.deepEqual(calls.map(row => row[0]), ['password', 'logout', 'replace'])
  assert.deepEqual(calls.at(-1)[1], { path: '/login', query: { passwordChanged: '1' } })
  assert.deepEqual({ ...state.password }, { current_password: '', new_password: '', confirm_password: '' })
})

test('password failure clears secrets, retains login and permits retry', async () => {
  const { state, calls } = await harness('views/shared/ProfileHome.vue', {
    expose: ['password', 'savePassword', 'notice', 'savingPassword'],
    mocks: { changePassword: async () => { throw failure('当前密码错误') } },
  })
  Object.assign(state.password, { current_password: 'bad', new_password: 'new', confirm_password: 'new' })
  await state.savePassword()
  assert.equal(state.password.new_password, '')
  assert.equal(state.savingPassword.value, false)
  assert.ok(!calls.some(row => row[0] === 'logout'))
})

test('admin creates a bound student, edits identity, resets password, and paginates by six', async () => {
  const { state, calls } = await harness('views/admin/UserManagement.vue', { role: 'admin',
    expose: ['page', 'pageView', 'users', 'form', 'openCreate', 'openEdit', 'saveUser', 'openReset', 'resetPassword', 'saveReset', 'formError'],
  })
  assert.equal(state.pageView.value.items.length, 6)
  state.openCreate()
  Object.assign(state.form, { username: 'new-student', password: 'secret', role: 'student' })
  await state.saveUser()
  assert.match(state.formError.value, /姓名、学号和班级/)
  assert.equal(calls.length, 0)
  Object.assign(state.form, { real_name: '测试学生', student_id: 'TEST-ID', class_name: '测试一班' })
  await state.saveUser()
  assert.equal(calls[0][0], 'create')
  assert.equal(state.form.password, '')
  assert.equal(state.page.value, 3)
  state.openEdit({ id: 2, username: 'student2', role: 'student', real_name: '学生', student_id: 'T2', class_name: '一班' })
  state.form.class_name = '二班'
  await state.saveUser()
  assert.deepEqual(calls.at(-1), ['update', 2, { role: 'student', real_name: '学生', student_id: 'T2', class_name: '二班' }])
  state.openReset({ id: 2, username: 'student2' })
  state.resetPassword.value = 'replacement'
  await state.saveReset()
  assert.deepEqual(calls.at(-1), ['reset', 2, { new_password: 'replacement' }])
  assert.equal(state.resetPassword.value, '')
})

test('admin deactivation needs confirmation, cancellation changes nothing, own account cannot be disabled', async () => {
  const { state, calls } = await harness('views/admin/UserManagement.vue', { role: 'admin', expose: ['toggleActive'] })
  await state.toggleActive({ id: 7, username: 'self', is_active: true })
  assert.equal(calls.length, 0)
  await state.toggleActive({ id: 8, username: 'other', is_active: true })
  assert.deepEqual(calls, [['confirm'], ['update', 8, { is_active: false }]])
  const cancel = await harness('views/admin/UserManagement.vue', { role: 'admin', expose: ['toggleActive'],
    mocks: { ElMessageBox: { confirm: async () => { throw new Error('cancel') } } },
  })
  await cancel.state.toggleActive({ id: 8, username: 'other', is_active: true })
  assert.equal(cancel.calls.length, 0)
})

test('login only provides authentication and clears password after success; errors show safe messages', async () => {
  const { state, calls, template } = await harness('views/auth/Login.vue', { expose: ['loginForm', 'loginFormRef', 'handleLogin'] })
  assert.ok(!template.includes('注册'))
  assert.ok(!template.includes('activeTab'))
  state.loginFormRef.value = { validate: async () => true }
  Object.assign(state.loginForm, { username: 'student', password: 'secret' })
  await state.handleLogin()
  assert.deepEqual(calls, [['login', { username: 'student', password: 'secret' }], ['push', '/student/dashboard']])
  assert.equal(state.loginForm.password, '')
  assert.equal(accountError({ response: { data: { detail: [{ msg: '字段格式错误' }] } } }), '字段格式错误')
})

test('account API functions forward only explicit fields to the intended endpoints', async () => {
  for (const [file, actions] of [
    ['api/auth.js', [['updateContact', ['/auth/me/contact', { email: null }]], ['changePassword', ['/auth/me/password', { new_password: 'x' }]]]],
    ['api/admin.js', [['createAdminUser', ['/admin/users', { username: 'test' }]], ['resetAdminPassword', ['/admin/users/9/reset-password', { new_password: 'x' }]]]],
  ]) {
    let source = await readFile(new URL('../src/' + file, import.meta.url), 'utf8')
    source = source.replace(/^import .*$/gm, '').replaceAll('export function', 'function')
    const api = new Function('request', source + '\nreturn {' + actions.map(a => a[0]).join(',') + '};')({ get: (...a) => a, post: (...a) => a, put: (...a) => a })
    for (const [name, expected] of actions) {
      assert.deepEqual(name === 'resetAdminPassword' ? api[name](9, expected[1]) : api[name](expected[1]), expected)
    }
  }
})
