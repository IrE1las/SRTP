export const roleLabels = { student: '学生', teacher: '教师', admin: '管理员' }
export const roleHomeMap = { student: '/student/dashboard', teacher: '/teacher/dashboard', admin: '/admin' }
export function navigationForRole(role) {
  if (role === 'student') return [
    { title: '首页', path: '/student/dashboard' },
    { title: '学习界面', path: '/student/learn', children: [
      { title: '理论学习', path: '/student/learn/theory' },
      { title: '操作学习', path: '/student/learn/operations' },
    ] },
    { title: '考试界面', path: '/student/exams', children: [], empty: 'null · 历史考试待S5实现' },
  ]
  if (role === 'teacher') return [
    { title: '首页', path: '/teacher/dashboard' },
    { title: '题目管理', path: '/teacher/questions' },
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
  return [{ title: '功能导航', items: navigationForRole(role).flatMap(item => [item, ...(item.children || [])]) }]
}
export function pageLabel(path, role) {
  if (path.startsWith('/teacher/questions/attempts/')) return '理论作答批改'
  if (path.startsWith('/teacher/questions/students/')) return '学生作答列表'
  if (path === '/teacher/questions') return '学生作答记录'
  if (path === '/student/learn/theory/attempts') return '我的作答'
  if (path.startsWith('/student/learn/theory/')) return '理论专题'
  return navigationGroups(role)[0].items.find(item => item.path === path)?.title || '实训平台'
}
