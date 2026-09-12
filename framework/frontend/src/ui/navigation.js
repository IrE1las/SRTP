import { Clock, Cpu, DataAnalysis, EditPen, Files, Guide, HomeFilled, School, SetUp, Share, UserFilled } from '@element-plus/icons-vue'
const study = { title: '学习空间', items: [
  { title: '学习概览', path: '/student/dashboard', icon: HomeFilled },
  { title: '练习大厅', path: '/student/lobby', icon: School },
  { title: '实验专题', path: '/student/lab-topics', icon: Guide },
  { title: '练习历史', path: '/student/history', icon: Clock },
] }
const diagnosis = { title: '专项诊断', items: [
  { title: '基础进路', path: '/student/interlocking-exam', icon: Guide, number: '01' },
  { title: '防护道岔', path: '/student/interlocking-exam-protective', icon: SetUp, number: '02' },
  { title: '带动道岔', path: '/student/interlocking-exam-driven', icon: Share, number: '03' },
  { title: '条件区段', path: '/student/interlocking-exam-conditional', icon: Files, number: '04' },
] }
const teaching = { title: '教学工作台', items: [
  { title: '批阅中心', path: '/teacher/grading', icon: EditPen },
  { title: '实验专题预览', path: '/teacher/lab-topics', icon: Guide },
  { title: '教学统计', path: '/teacher/dashboard', icon: DataAnalysis },
  { title: '仿真练习管理', path: '/teacher/exercises', icon: Files },
  { title: '新建仿真练习', path: '/teacher/exercises/new', icon: EditPen },
] }
const contentManagement = { title: '出题与批阅', items: [
  { title: '题库工作台', path: '/admin/questions', icon: Files },
  { title: '自行出题', path: '/admin/questions/new', icon: EditPen },
  { title: '批阅中心', path: '/admin/grading', icon: DataAnalysis },
] }
const admin = { title: '平台管理', items: [
  { title: '系统管理', path: '/admin', icon: UserFilled },
  { title: 'AI 设置', path: '/admin/ai-settings', icon: Cpu },
] }
export const roleLabels = { student: '学生', teacher: '教师', admin: '管理员' }
export function navigationGroups(role) {
  return role === 'admin' ? [contentManagement, study, diagnosis, {...teaching,items:teaching.items.filter(i=>!['/teacher/grading','/teacher/lab-topics'].includes(i.path))}, admin] : role === 'teacher' ? [teaching] : role === 'student' ? [study, diagnosis] : []
}
export function pageLabel(path, role) {
  return navigationGroups(role).flatMap(group => group.items).find(item => item.path === path)?.title
    || (path.startsWith('/admin/questions/') ? '编辑题目' : path.startsWith('/student/exercises/') ? '进路实训' : path.startsWith('/student/history/') ? '练习回放' : path.startsWith('/student/shunting-questions') ? '原图调车题库' : path.endsWith('/edit') ? '编辑练习' : '实训工作台')
}
