import { Calendar, Clock, Cpu, DataAnalysis, EditPen, Files, Guide, Monitor, UserFilled } from '@element-plus/icons-vue'
const study = { title: '学习空间', items: [
  { title: '客观题库', path: '/student/chapter-bank', icon: Files },
  { title: '实验专题', path: '/student/lab-topics', icon: Guide },
  { title: '仿真操作台', path: '/student/simulation-console', icon: Monitor },
] }
const records = { title: '学习记录', items: [{ title: '实验学习记录', path: '/student/history', icon: Clock }] }
const teacherWorkspace = { title: '教学工作台', items: [
  { title: '客观题库', path: '/teacher/chapter-bank', icon: Files },
  { title: '批阅中心', path: '/teacher/grading', icon: EditPen },
  { title: '教学统计', path: '/teacher/dashboard', icon: DataAnalysis },
] }
const assessments = { title: '操作与考试', items: [
  { title: '操作学习', path: '/student/learn/operations', icon: Monitor },
  { title: '操作学习记录', path: '/student/learn/operations/history', icon: Clock },
  { title: '正式考试', path: '/student/exams', icon: Calendar },
  { title: '历史考试与成绩', path: '/student/exams/history', icon: DataAnalysis },
] }
const operationTeaching = { title: '操作与考试管理', items: [
  { title: '操作题录制与管理', path: '/operations/manage', icon: Monitor },
  { title: '操作学习批阅', path: '/operations/reviews', icon: EditPen },
  { title: '正式考试管理', path: '/exams/manage', icon: Calendar },
  { title: '考试批阅', path: '/exams/grading', icon: EditPen },
] }
const account = { title: '账号', items: [{ title: '个人资料与密码', path: '/account', icon: UserFilled }] }
const admin = { title: '平台管理', items: [
  { title: '系统管理', path: '/admin', icon: UserFilled },
  { title: '用户管理', path: '/admin/users', icon: UserFilled },
  { title: 'AI 设置', path: '/admin/ai-settings', icon: Cpu },
  { title: '资料库', path: '/admin/knowledge', icon: Files },
  { title: '实验题目', path: '/admin/questions', icon: Files },
] }
export const roleLabels = { student: '学生', teacher: '教师', admin: '管理员' }
export function navigationGroups(role) {
  return role === 'admin' ? [admin, account] : role === 'teacher' ? [teacherWorkspace, records, operationTeaching, account] : role === 'student' ? [study, records, assessments, account] : []
}
export function teacherDestination(path) {
  if (path === '/student/chapter-bank' || path.startsWith('/student/chapter-bank/')) return '/teacher/chapter-bank'
  if (['/student/lab-topics','/teacher/lab-topics'].includes(path)) return '/teacher/grading'
  if (path === '/student/simulation-console' || path === '/teacher/exercises' || path.startsWith('/teacher/exercises/')) return '/teacher/dashboard'
  return null
}
export function pageLabel(path, role) {
  if (path === '/teacher/chapter-bank') return '客观题库管理'
  if (path === '/exams/grading') return '考试批阅'
  if (path === '/student/chapter-bank/all') return '全部题目'
  if (path.startsWith('/student/exams/attempts/')) return '正式考试'
  if (path.startsWith('/exams/manage/attempts/')) return '考试批阅'
  if (path.startsWith('/exams/manage/')) return '考试设置'
  if (/^\/operations\/manage\/.*\/record$/.test(path)) return '录制标准操作'
  if (/^\/operations\/manage\/.*\/review$/.test(path)) return '检查与发布'
  if (path.startsWith('/operations/manage/')) return '操作题设置'
  if (path.startsWith('/operations/reviews/')) return '操作学习批阅'
  if (path.startsWith('/student/learn/operations/attempts/')) return '操作作答'

  return navigationGroups(role).flatMap(group => group.items).find(item => item.path === path)?.title
    || ({ '/student/dashboard': '学习概览', '/student/lobby': '练习大厅', '/teacher/lab-topics': '实验专题' })[path]
    || (path.startsWith('/student/chapter-bank') ? '客观题库' : path.startsWith('/admin/questions/') ? '编辑题目' : path.startsWith('/student/exercises/') ? '进路实训' : path.startsWith('/student/history/') ? '实验回放' : path.startsWith('/student/shunting-questions') ? '原图调车题库' : path.endsWith('/edit') ? '编辑练习' : '实训工作台')
}
