export const roleLabels = { student: '学生', teacher: '教师', admin: '管理员' }
export const roleHomeMap = { student: '/student/dashboard', teacher: '/teacher/dashboard', admin: '/admin' }
export function navigationForRole(role) {
  if (role === 'student') return [
    { title: '首页', path: '/student/dashboard' },
    { title: '学习界面', path: '/student/learn', children: [
      { title: '理论学习', path: '/student/learn/theory' },
      { title: '操作学习', path: '/student/learn/operations' },
    ] },
    { title: '考试界面', path: '/student/exams', overview: true, children: [{ title: '历史考试', path: '/student/exams/history' }] },
  ]
  if (role === 'teacher') return [
    { title: '首页', path: '/teacher/dashboard' },
    { title: '题目管理', path: '/teacher/questions', children: [
      { title: '理论学习', path: '/teacher/questions' },
      { title: '操作学习', path: '/operations/manage' },
    ] },
    { title: '考试管理', path: '/teacher/exams' },
  ]
  if (role === 'admin') return [
    { title: '首页', path: '/admin' },
    { title: '用户管理', path: '/admin/users' },
    { title: 'AI设置', path: '/admin/ai-settings' },
  ]
  return []
}
export function navigationGroups(role) {
  return [{ title: '功能导航', items: navigationForRole(role).flatMap(item => item.children?.length ? item.children : [item]) }]
}
export function pageLabel(path, role) {
  if (path === '/student/exams') return '考试界面'
  if (path === '/student/exams/history') return '历史考试'
  if (path.startsWith('/exams/manage/attempts/')) return '考试批阅'
  if (path === '/exams/manage/new') return '新建考试'
  if (/^\/exams\/manage\/\d+$/.test(path)) return '考试详情'
  if (path === '/exams/manage') return '考试管理'
  if (path === '/operations/reviews') return '操作批改'
  if (path.startsWith('/operations/reviews/')) return '操作作答批改'
  if (path === '/student/learn/operations/history') return '我的操作记录'
  if (path.startsWith('/student/learn/operations/attempts/')) return '操作答题'
  if (path === '/operations/manage') return '操作题管理'
  if (path === '/operations/manage/new' || /^\/operations\/manage\/\d+\/edit$/.test(path)) return '题目设置'
  if (/^\/operations\/manage\/\d+\/review$/.test(path)) return '检查与发布'
  if (/^\/operations\/manage\/\d+\/record$/.test(path)) return '站场操作台'
  if (path.startsWith('/teacher/questions/attempts/')) return '理论作答批改'
  if (path.startsWith('/teacher/questions/students/')) return '学生作答列表'
  if (path === '/teacher/questions') return '理论学习'
  if (path === '/student/learn/theory/attempts') return '我的作答'
  if (path.startsWith('/student/learn/theory/')) return '理论专题'
  return navigationGroups(role)[0].items.find(item => item.path === path)?.title || '实训平台'
}
